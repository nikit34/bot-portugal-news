import html
import time
import asyncio
import logging
from datetime import datetime, timezone

import requests

from src.processor.history_comparator import make_head
from src.producers.telegram.debug_chat import send_debug_message
from src.utils.notify import redact_secrets
from src.static.settings import (
    INSIGHTS_REPORT_ENABLED,
    INSIGHTS_REPORT_HOUR,
    INSIGHTS_MEDIA_LIMIT,
    INSIGHTS_TOP_N,
    GRAPH_API_BASE,
    CMP_FOLLOWERS_TARGET,
    CMP_WATCH_MINUTES_TARGET,
    CMP_FOLLOWERS_TARGET_REELS,
    CMP_WATCH_MINUTES_TARGET_REELS,
)

logger = logging.getLogger('app')

_GRAPH = GRAPH_API_BASE


def should_report_insights(current_hour=None):
    # Stateless «раз в сутки»: запускаем только когда UTC-час совпал с заданным.
    if not INSIGHTS_REPORT_ENABLED:
        return False
    if current_hour is None:
        current_hour = datetime.now(timezone.utc).hour
    return current_hour == INSIGHTS_REPORT_HOUR


def get_instagram_media_insights(access_token, ig_user_id, limit, top_n):
    # Одним запросом тянем последние посты с like_count/comments_count (обычные
    # поля, стабильны между версиями), ранжируем по вовлечённости и только для
    # топ-N добираем reach (отдельный вызов insights) — так число запросов
    # ограничено top_n, а не всем списком.
    media = _fetch_recent_media(access_token, ig_user_id, limit)
    ranked = sorted(
        media,
        key=lambda m: (m.get('like_count', 0) or 0) + (m.get('comments_count', 0) or 0),
        reverse=True,
    )[:top_n]
    items = []
    for m in ranked:
        items.append({
            'head': make_head(m.get('caption', '') or ''),
            'media_type': m.get('media_type', ''),
            'likes': m.get('like_count', 0) or 0,
            'comments': m.get('comments_count', 0) or 0,
            'reach': _fetch_media_reach(access_token, m.get('id')),
        })
    return items


def _fetch_recent_media(access_token, ig_user_id, limit):
    # Best-effort/fail-open: если IG-аккаунт недоступен (не привязан к Странице, нет
    # прав, code 100/33) — возвращаем [], а НЕ роняем весь прогон. Раньше raise отсюда
    # прокидывался до верхнего обработчика main и убивал бот (в т.ч. после публикации).
    url = _GRAPH + ig_user_id + '/media'
    params = {
        'fields': 'id,caption,media_type,like_count,comments_count,timestamp',
        'limit': limit,
        'access_token': access_token,
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get('data', [])
    except Exception as e:
        logger.warning(redact_secrets(f"[insights] IG media list unavailable for {ig_user_id}: {e}"))
        return []


def _fetch_media_insights(access_token, media_id, metrics):
    # GET /{media}/insights для списка метрик; возвращает {name: value}. Best-effort:
    # на любой ошибке (нет instagram_manage_insights / метрика не поддерживается этим
    # media_type или версией API) возвращаем {} — вызывающий деградирует, а не теряет
    # весь пост. ВАЖНО: одна неподдерживаемая метрика 400-ит ВЕСЬ запрос, поэтому
    # reward-путь просит метрики группами с фолбэком (см. _fetch_ig_reward_insights).
    if not media_id or not metrics:
        return {}
    url = _GRAPH + media_id + '/insights'
    params = {'metric': ','.join(metrics), 'access_token': access_token}
    out = {}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        for metric in response.json().get('data', []):
            values = metric.get('values') or [{}]
            out[metric.get('name')] = values[0].get('value')
    except Exception as e:
        logger.warning(redact_secrets(f"[insights] IG insights {metrics} unavailable for {media_id}: {e}"))
    return out


def _fetch_media_reach(access_token, media_id):
    # reach живёт на endpoint insights и требует instagram_manage_insights.
    # Best-effort: если метрики/права нет — возвращаем None, пост покажем без охвата.
    if not media_id:
        return None
    return _fetch_media_insights(access_token, media_id, ['reach']).get('reach')


def _fetch_ig_reward_insights(access_token, media_id, media_type):
    # Метрики ранжирования для reward: reach + saved + shares (репост + отправка в DM),
    # а для reels/video ещё ig_reels_avg_watch_time (средний досмотр, мс). Просим богатый
    # набор одним вызовом и деградируем так, чтобы НИКОГДА не потерять reach (якорь):
    # reach,saved,shares -> reach,saved -> reach. `shares` и reels-метрики новее и на
    # старом Graph (v18) могут быть недоступны — тогда молча остаёмся с reach(+saved),
    # а sends/watch подтянутся после апгрейда версии API.
    if not media_id:
        return {}
    got = _fetch_media_insights(access_token, media_id, ['reach', 'saved', 'shares'])
    if 'reach' not in got:
        got = _fetch_media_insights(access_token, media_id, ['reach', 'saved'])
    if 'reach' not in got:
        got = _fetch_media_insights(access_token, media_id, ['reach'])
    if (media_type or '').upper() in ('VIDEO', 'REELS'):
        watch = _fetch_media_insights(access_token, media_id, ['ig_reels_avg_watch_time'])
        if watch.get('ig_reels_avg_watch_time') is not None:
            got['ig_reels_avg_watch_time'] = watch['ig_reels_avg_watch_time']
    return got


def _parse_media_timestamp(value):
    # IG timestamps look like '2026-06-12T21:00:00+0000'.
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z').timestamp()
    except (ValueError, TypeError):
        return None


def get_instagram_reach_by_head(access_token, ig_user_id, limit, min_age_seconds, now):
    # For the learning loop: reach keyed by post head, only for media old enough
    # that reach has matured. Heads match make_head(caption) == the publish key.
    media = _fetch_recent_media(access_token, ig_user_id, limit)
    reach_by_head = {}
    for item in media:
        caption = item.get('caption')
        if not caption:
            continue
        ts = _parse_media_timestamp(item.get('timestamp'))
        if ts is None or (now - ts) < min_age_seconds:
            continue
        reach = _fetch_media_reach(access_token, item.get('id'))
        if reach is not None:
            reach_by_head[make_head(caption)] = reach
    return reach_by_head


def get_instagram_metrics_by_head(access_token, ig_user_id, limit, min_age_seconds, now):
    # Reward-путь: как get_instagram_reach_by_head, но возвращает полный набор метрик
    # на пост {reach, saves, shares, watch, likes, comments}. like_count/comments_count —
    # обычные поля media (бесплатно, уже в выдаче _fetch_recent_media); reach/saved/
    # shares/watch — insights-вызов (нужно instagram_manage_insights), тянем группами
    # с фолбэком. watch = средний досмотр reels в СЕКУНДАХ. Только для зрелых постов.
    media = _fetch_recent_media(access_token, ig_user_id, limit)
    metrics_by_head = {}
    for item in media:
        caption = item.get('caption')
        if not caption:
            continue
        ts = _parse_media_timestamp(item.get('timestamp'))
        if ts is None or (now - ts) < min_age_seconds:
            continue
        insights = _fetch_ig_reward_insights(access_token, item.get('id'), item.get('media_type'))
        watch_ms = insights.get('ig_reels_avg_watch_time')
        metrics_by_head[make_head(caption)] = {
            'reach': insights.get('reach'),
            'saves': insights.get('saved'),
            'shares': insights.get('shares'),                       # репост + sends в DM
            'watch': (watch_ms / 1000.0) if watch_ms is not None else None,  # мс -> сек
            'likes': item.get('like_count', 0) or 0,
            'comments': item.get('comments_count', 0) or 0,
        }
    return metrics_by_head


def get_facebook_post_insights(access_token, post_id):
    # Метрики на FB-пост по сохранённому page-post id. Best-effort, fail-open.
    # Reach НЕ тянем: post-level reach/impressions метрики (post_impressions_unique
    # и пр.) удалены Meta в v18 — отдают "(#100) not a valid insights metric" даже
    # с Page-токеном и read_insights, так что запрашивать их бессмысленно (только
    # спам в логах + лишние вызовы). Вовлечённость берём ПОЛЯМИ объекта (shares,
    # comments.summary, reactions.summary) — они работают и без спец-прав. На FB
    # сигнал оптимизатора держится на вовлечённости; reach закрывает Instagram.
    metrics = {}
    if not post_id:
        return metrics
    # Полноценный page-post id вида '{pageid}_{postid}' адресует story-узел поста —
    # у него есть shares + comments + reactions. Голый числовой id — это media-объект
    # (video из /videos отдаёт только 'id', без post_id): у Video/Photo НЕТ поля
    # 'shares', и запрос его вызывает Graph error #100 → 400 на весь вызов, теряя и
    # comments/reactions. Поэтому для голого id просим только то, что узел отдаёт.
    is_page_post = '_' in str(post_id)
    fields = ('shares,comments.summary(true),reactions.summary(true)' if is_page_post
              else 'comments.summary(true),reactions.summary(true)')
    try:
        url = _GRAPH + post_id
        params = {
            'fields': fields,
            'access_token': access_token,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        metrics['shares'] = (data.get('shares') or {}).get('count', 0)
        metrics['comments'] = ((data.get('comments') or {}).get('summary') or {}).get('total_count', 0)
        metrics['likes'] = ((data.get('reactions') or {}).get('summary') or {}).get('total_count', 0)
    except Exception as e:
        logger.warning(redact_secrets(f"[insights] FB post engagement unavailable for {post_id}: {e}"))
    return metrics


def _fetch_object_insights(access_token, obj_id, connection, metric, period=None):
    # Общий GET /{id}/{connection}?metric=... -> {name: value}. Одна неподдерживаемая
    # метрика 400-ит ВЕСЬ запрос, поэтому вызывающие просят метрики по одной/группами.
    # Best-effort: любая ошибка => {}, прогон не падает.
    url = _GRAPH + str(obj_id) + '/' + connection
    params = {'metric': metric, 'access_token': access_token}
    if period:
        params['period'] = period
    out = {}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        for entry in response.json().get('data', []):
            values = entry.get('values') or [{}]
            out[entry.get('name')] = values[-1].get('value')
    except Exception as e:
        logger.warning(redact_secrets(
            f"[insights] {connection} {metric} unavailable for {obj_id}: {e}"))
    return out


# Пока страница не онбордена в Content Monetization, метрики заработка не отдаются
# НИ ДЛЯ ОДНОГО поста. Без этого предохранителя каждый скоринг делал бы по два
# заведомо провальных запроса на каждый зрелый пост (десятки лишних вызовов к Graph
# и столько же WARNING в логах). Первый отказ гасит попытки до конца прогона; каждый
# прогон — новый процесс, поэтому появление монетизации подхватится само.
_earnings_unavailable = False


def get_facebook_post_earnings(access_token, post_id):
    # Фактический заработок поста, USD. content_monetization_earnings появилась в
    # Graph v23.0 и отдаётся ТОЛЬКО странице, онбординг которой в Content
    # Monetization завершён; у остальных — ошибка/пусто, и это нормальный путь
    # (fail-open => None, денежный член reward просто равен нулю).
    global _earnings_unavailable
    if not post_id or _earnings_unavailable:
        return None
    got = _fetch_object_insights(
        access_token, post_id, 'insights', 'content_monetization_earnings', period='lifetime')
    value = got.get('content_monetization_earnings')
    if value is None:
        got = _fetch_object_insights(
            access_token, post_id, 'insights', 'monetization_approximate_earnings',
            period='lifetime')
        value = got.get('monetization_approximate_earnings')
    if value is None:
        _earnings_unavailable = True
        logger.info("[insights] earnings metrics unavailable (page not onboarded to "
                    "Content Monetization?); skipping earnings for the rest of this run")
    return _as_number(value)


def get_facebook_video_watch_minutes(access_token, video_id):
    # Суммарное время просмотра видео в МИНУТАХ. total_video_view_total_time приходит
    # в миллисекундах на /{video-id}/video_insights. Это валюта порога допуска в
    # программу монетизации (минуты просмотра за 60 дней) и лучший из доступных
    # прокси «квалифицированного» просмотра. Для фото эндпоинта нет => None.
    if not video_id:
        return None
    got = _fetch_object_insights(
        access_token, video_id, 'video_insights', 'total_video_view_total_time')
    ms = _as_number(got.get('total_video_view_total_time'))
    return (ms / 60000.0) if ms is not None else None


def _as_number(value):
    # Метрики инсайтов приходят числом, а с разбивкой — словарём {ключ: число};
    # для нашей свёртки достаточно суммы. Всё непарсимое => None.
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        nums = [v for v in value.values() if isinstance(v, (int, float))]
        return float(sum(nums)) if nums else None
    return None


def get_facebook_metrics_by_head(access_token, pending, now, min_age_seconds,
                                 with_earnings=False, with_watch_time=False):
    # FB-метрики, привязанные к посту по СОХРАНЁННОМУ fb_id (точная атрибуция, без
    # матча по тексту). Только для зрелых pending-записей, у которых есть fb_id.
    # with_earnings/with_watch_time добавляют денежные члены reward: заработок поста
    # и суммарные минуты просмотра. Видео просим по media-id (fb_media_id): у поста
    # вида '{page}_{post}' нет video_insights, они живут на самом видео-объекте.
    metrics_by_head = {}
    for post in pending or []:
        fb_id = post.get('fb_id')
        head = post.get('head')
        if not fb_id or not head:
            continue
        if (now - post.get('ts', 0)) < min_age_seconds:
            continue
        metrics = get_facebook_post_insights(access_token, fb_id)
        if with_earnings:
            earnings = get_facebook_post_earnings(access_token, fb_id)
            if earnings is not None:
                metrics['earnings'] = earnings
        if with_watch_time and post.get('is_video'):
            minutes = get_facebook_video_watch_minutes(
                access_token, post.get('fb_media_id') or fb_id)
            if minutes is not None:
                metrics['watch_total'] = minutes
        if metrics:
            metrics_by_head[head] = metrics
    return metrics_by_head


# Охват страницы: page_impressions_unique выведена из строя 15.06.2026 ДЛЯ ВСЕХ
# версий API (не только старых) — запрос отдаёт «(#100) not a valid metric».
# Замена от Meta — page_total_media_view_unique. Пробуем новую, откатываемся на
# старую: так дайджест работает и на страницах/версиях, где старая ещё жива.
_PAGE_REACH_METRICS = ('page_total_media_view_unique', 'page_impressions_unique')


def get_facebook_page_insights(access_token, page_id):
    # Охват и вовлечённость страницы за сутки. Best-effort (нужно право read_insights).
    stats = {}
    for reach_metric in _PAGE_REACH_METRICS:
        got = _fetch_object_insights(
            access_token, page_id, 'insights',
            reach_metric + ',page_post_engagements', period='day')
        if got:
            # Ключ нормализуем: остальной код (дайджест) знает одно имя.
            reach = got.get(reach_metric)
            if reach is not None:
                stats['page_reach'] = reach
            if got.get('page_post_engagements') is not None:
                stats['page_post_engagements'] = got['page_post_engagements']
            if stats:
                return stats
    return stats


def get_facebook_page_monetization(access_token, page_id, window_days=60):
    # Прогресс к допуску в Content Monetization: подписчики + минуты просмотра за
    # трейлинговое окно + заработок страницы. Всё best-effort и по отдельности:
    # у не-монетизированной страницы часть метрик недоступна, и это ожидаемо.
    out = {}
    try:
        response = requests.get(
            _GRAPH + str(page_id),
            params={'fields': 'followers_count,fan_count', 'access_token': access_token})
        response.raise_for_status()
        data = response.json()
        out['followers'] = data.get('followers_count') or data.get('fan_count')
    except Exception as e:
        logger.warning(redact_secrets(f"[insights] FB followers unavailable: {e}"))

    since = int(time.time()) - window_days * 86400
    minutes = _fetch_page_watch_minutes(access_token, page_id, since)
    if minutes is not None:
        out['watch_minutes_60d'] = minutes
        out['watch_window_days'] = window_days

    earnings = _fetch_object_insights(
        access_token, page_id, 'insights', 'content_monetization_earnings', period='days_28')
    value = _as_number(earnings.get('content_monetization_earnings'))
    if value is not None:
        out['earnings_28d'] = value
    return out


def _fetch_page_watch_minutes(access_token, page_id, since):
    # Суммарные минуты просмотра страницы за окно: page_video_view_time приходит
    # днями (мс/день), поэтому суммируем весь ряд, а не берём последнее значение.
    url = _GRAPH + str(page_id) + '/insights'
    params = {
        'metric': 'page_video_view_time',
        'period': 'day',
        'since': since,
        'until': int(time.time()),
        'access_token': access_token,
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        total_ms = 0
        found = False
        for entry in response.json().get('data', []):
            for point in entry.get('values') or []:
                value = _as_number(point.get('value'))
                if value is not None:
                    total_ms += value
                    found = True
        return (total_ms / 60000.0) if found else None
    except Exception as e:
        logger.warning(redact_secrets(f"[insights] FB page watch time unavailable: {e}"))
        return None


_WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


def _fmt_dow_hour(key):
    # 'wday-hour' (напр. '2-14') -> 'Ср 14:00'. На непарсимый ключ — как есть.
    try:
        dow, hour = str(key).split('-')
        return f'{_WEEKDAYS[int(dow)]} {int(hour):02d}:00'
    except (ValueError, IndexError):
        return str(key)


def _fmt_reward(value):
    # Округление до целого прятало ВСЮ разницу между источниками: 0.199 и строгий
    # ноль печатались одинаково («0»), хотя это принципиально разные вещи — след
    # вовлечённости против её полного отсутствия на десятках постов подряд.
    # Поэтому точность плавающая: крупные значения (минуты просмотра дайджеста,
    # старые reach-числа) остаются целыми и читаемыми, мелкие показываются целиком,
    # а ненулевая пыль уходит в экспоненту, чтобы её не спутать с настоящим нулём.
    value = float(value or 0)
    if value == 0:
        return '0'
    if abs(value) >= 10:
        return str(round(value))
    if abs(value) >= 0.01:
        return f'{value:.2f}'
    return f'{value:.1e}'


def _progress_bar(done, target, width=10):
    filled = 0 if target <= 0 else min(width, int(width * done / target))
    return '█' * filled + '░' * (width - filled)


def _monetization_lines(monetization):
    # Расстояние до денег: подписчики и минуты просмотра против порога допуска в
    # Content Monetization. Показываем ОБА трека — мягкий (reels: 5k/60k) и полный
    # (10k/600k), чтобы было видно, какой берётся первым. Нет данных — нет блока.
    if not monetization:
        return []
    followers = monetization.get('followers')
    minutes = monetization.get('watch_minutes_60d')
    earnings = monetization.get('earnings_28d')
    if followers is None and minutes is None and earnings is None:
        return []

    lines = ['\n<b>💰 Допуск в монетизацию</b>']
    for label, f_target, m_target in (
            ('reels-трек', CMP_FOLLOWERS_TARGET_REELS, CMP_WATCH_MINUTES_TARGET_REELS),
            ('полный', CMP_FOLLOWERS_TARGET, CMP_WATCH_MINUTES_TARGET)):
        parts = []
        if followers is not None:
            parts.append(f'{_progress_bar(followers, f_target)} {followers}/{f_target} подписчиков')
        if minutes is not None:
            parts.append(
                f'{_progress_bar(minutes, m_target)} {round(minutes)}/{m_target} мин за '
                f'{monetization.get("watch_window_days", 60)}д')
        if parts:
            lines.append(f'<b>{label}</b>')
            lines.extend('• ' + p for p in parts)
    if earnings is not None:
        lines.append(f'• заработок за 28д: ${earnings:.2f}')
    return lines


def build_insights_report(ig_items, fb_stats, source_ranking=None, hour_ranking=None,
                          format_ranking=None, variant_ranking=None, dow_hour_ranking=None,
                          winners=None, monetization=None, digest_ranking=None):
    lines = ['📊 <b>Insights</b>']

    if winners:
        lines.append('\n<b>Свежие «победители» (reward)</b>')
        for i, w in enumerate(winners, 1):
            head = html.escape((w.get('head') or '(без подписи)')[:60])
            source = html.escape(str(w.get('source', '') or ''))
            lines.append(f'{i}. {head} — {_fmt_reward(w.get("reward", 0.0))} ({source})')

    fb_reach = fb_stats.get('page_reach')
    fb_eng = fb_stats.get('page_post_engagements')
    if fb_reach is not None or fb_eng is not None:
        lines.append('\n<b>Facebook (страница, сутки)</b>')
        if fb_reach is not None:
            lines.append(f'• охват: {fb_reach}')
        if fb_eng is not None:
            lines.append(f'• вовлечённость: {fb_eng}')

    money_lines = _monetization_lines(monetization)
    if money_lines:
        lines.extend(money_lines)

    if ig_items:
        lines.append('\n<b>Instagram — топ постов</b>')
        for i, item in enumerate(ig_items, 1):
            head = html.escape((item['head'] or '(без подписи)')[:60])
            reach = item['reach'] if item['reach'] is not None else '—'
            lines.append(
                f'{i}. {head}\n   👁 {reach} · ❤️ {item["likes"]} · 💬 {item["comments"]}')

    if source_ranking:
        lines.append('\n<b>Источники по reward (средн.)</b>')
        for i, (name, reach_avg, n) in enumerate(source_ranking, 1):
            lines.append(f'{i}. {html.escape(name)} — {_fmt_reward(reach_avg)} (n={n})')

    if hour_ranking:
        lines.append('\n<b>Лучшие часы по reward (UTC, средн.)</b>')
        for i, (hour, reach_avg, n) in enumerate(hour_ranking, 1):
            lines.append(f'{i}. {int(hour):02d}:00 — {_fmt_reward(reach_avg)} (n={n})')

    if dow_hour_ranking:
        lines.append('\n<b>Лучшие слоты день×час (UTC, средн.)</b>')
        for i, (key, reward_avg, n) in enumerate(dow_hour_ranking, 1):
            lines.append(f'{i}. {_fmt_dow_hour(key)} — {_fmt_reward(reward_avg)} (n={n})')

    if format_ranking:
        lines.append('\n<b>Форматы по reward (средн.)</b>')
        for name, reward_avg, n in format_ranking:
            lines.append(f'• {html.escape(str(name))}: {_fmt_reward(reward_avg)} (n={n})')

    if digest_ranking:
        # Отдельной строкой: reward дайджеста живёт в своём бакете, чтобы не
        # перекашивать пост-уровневую статистику, но сравнить их полезно —
        # это и есть ответ, окупается ли длинный ролик против обычных постов.
        lines.append('\n<b>Длинный дайджест-ролик (reward, средн.)</b>')
        for name, reward_avg, n in digest_ranking:
            lines.append(f'• {html.escape(str(name))}: {_fmt_reward(reward_avg)} (n={n})')

    if variant_ranking:
        lines.append('\n<b>Хэштеги по reward (средн.)</b>')
        for name, reward_avg, n in variant_ranking:
            lines.append(f'• {html.escape(str(name))}: {_fmt_reward(reward_avg)} (n={n})')

    if len(lines) == 1:
        lines.append('\nданные недоступны (нет прав read_insights / instagram_manage_insights?)')

    return '\n'.join(lines)


async def report_insights(graph, client, context, source_ranking=None, hour_ranking=None,
                          format_ranking=None, variant_ranking=None, dow_hour_ranking=None,
                          winners=None, digest_ranking=None):
    ig_items = []
    fb_stats = {}
    ig_user_id = context.get('self_instagram_channel')
    if ig_user_id:
        try:
            ig_items = await asyncio.to_thread(
                get_instagram_media_insights,
                graph.access_token, ig_user_id, INSIGHTS_MEDIA_LIMIT, INSIGHTS_TOP_N)
        except Exception as e:
            logger.warning(redact_secrets(f"[insights] IG media insights failed: {e}"))
    try:
        fb_stats = await asyncio.to_thread(
            get_facebook_page_insights, graph.access_token, context['self_facebook_page_id'])
    except Exception as e:
        logger.warning(redact_secrets(f"[insights] FB page insights failed: {e}"))

    monetization = {}
    try:
        monetization = await asyncio.to_thread(
            get_facebook_page_monetization, graph.access_token, context['self_facebook_page_id'])
    except Exception as e:
        logger.warning(redact_secrets(f"[insights] FB monetization progress failed: {e}"))

    report = build_insights_report(
        ig_items, fb_stats, source_ranking, hour_ranking, format_ranking, variant_ranking,
        dow_hour_ranking, winners=winners, monetization=monetization,
        digest_ranking=digest_ranking)
    await send_debug_message(report, client, context)
    logger.info("[insights] report sent to debug chat")
