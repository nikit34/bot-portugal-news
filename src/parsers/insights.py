import html
import asyncio
import logging
from datetime import datetime, timezone

import requests

from src.processor.history_comparator import make_head
from src.producers.telegram.telegram_api import send_message_api
from src.static.settings import (
    INSIGHTS_REPORT_ENABLED,
    INSIGHTS_REPORT_HOUR,
    INSIGHTS_MEDIA_LIMIT,
    INSIGHTS_TOP_N,
)

logger = logging.getLogger('app')

_GRAPH = 'https://graph.facebook.com/v18.0/'


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
    url = _GRAPH + ig_user_id + '/media'
    params = {
        'fields': 'id,caption,media_type,like_count,comments_count,timestamp',
        'limit': limit,
        'access_token': access_token,
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get('data', [])


def _fetch_media_reach(access_token, media_id):
    # reach живёт на endpoint insights и требует instagram_manage_insights.
    # Best-effort: если метрики/права нет — возвращаем None, пост покажем без охвата.
    if not media_id:
        return None
    url = _GRAPH + media_id + '/insights'
    params = {'metric': 'reach', 'access_token': access_token}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        for metric in response.json().get('data', []):
            if metric.get('name') == 'reach':
                values = metric.get('values') or [{}]
                return values[0].get('value')
    except Exception as e:
        logger.warning(f"[insights] IG reach unavailable for {media_id}: {e}")
    return None


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
    # Reward-путь: как get_instagram_reach_by_head, но возвращает полный набор
    # метрик на пост {reach, likes, comments}. like_count/comments_count — обычные
    # поля media (бесплатно, уже в выдаче _fetch_recent_media); reach — отдельный
    # insights-вызов (нужно instagram_manage_insights). Только для зрелых постов.
    media = _fetch_recent_media(access_token, ig_user_id, limit)
    metrics_by_head = {}
    for item in media:
        caption = item.get('caption')
        if not caption:
            continue
        ts = _parse_media_timestamp(item.get('timestamp'))
        if ts is None or (now - ts) < min_age_seconds:
            continue
        metrics_by_head[make_head(caption)] = {
            'reach': _fetch_media_reach(access_token, item.get('id')),
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
    try:
        url = _GRAPH + post_id
        params = {
            'fields': 'shares,comments.summary(true),reactions.summary(true)',
            'access_token': access_token,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        metrics['shares'] = (data.get('shares') or {}).get('count', 0)
        metrics['comments'] = ((data.get('comments') or {}).get('summary') or {}).get('total_count', 0)
        metrics['likes'] = ((data.get('reactions') or {}).get('summary') or {}).get('total_count', 0)
    except Exception as e:
        logger.warning(f"[insights] FB post engagement unavailable for {post_id}: {e}")
    return metrics


def get_facebook_metrics_by_head(access_token, pending, now, min_age_seconds):
    # FB-метрики, привязанные к посту по СОХРАНЁННОМУ fb_id (точная атрибуция, без
    # матча по тексту). Только для зрелых pending-записей, у которых есть fb_id.
    metrics_by_head = {}
    for post in pending or []:
        fb_id = post.get('fb_id')
        head = post.get('head')
        if not fb_id or not head:
            continue
        if (now - post.get('ts', 0)) < min_age_seconds:
            continue
        metrics = get_facebook_post_insights(access_token, fb_id)
        if metrics:
            metrics_by_head[head] = metrics
    return metrics_by_head


def get_facebook_page_insights(access_token, page_id):
    # Охват и вовлечённость страницы за сутки. Best-effort (нужно право read_insights).
    url = _GRAPH + page_id + '/insights'
    params = {
        'metric': 'page_impressions_unique,page_post_engagements',
        'period': 'day',
        'access_token': access_token,
    }
    stats = {}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        for metric in response.json().get('data', []):
            values = metric.get('values') or [{}]
            stats[metric.get('name')] = values[-1].get('value')
    except Exception as e:
        logger.warning(f"[insights] FB page insights unavailable: {e}")
    return stats


_WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


def _fmt_dow_hour(key):
    # 'wday-hour' (напр. '2-14') -> 'Ср 14:00'. На непарсимый ключ — как есть.
    try:
        dow, hour = str(key).split('-')
        return f'{_WEEKDAYS[int(dow)]} {int(hour):02d}:00'
    except (ValueError, IndexError):
        return str(key)


def build_insights_report(ig_items, fb_stats, source_ranking=None, hour_ranking=None,
                          format_ranking=None, variant_ranking=None, dow_hour_ranking=None):
    lines = ['📊 <b>Insights</b>']

    fb_reach = fb_stats.get('page_impressions_unique')
    fb_eng = fb_stats.get('page_post_engagements')
    if fb_reach is not None or fb_eng is not None:
        lines.append('\n<b>Facebook (страница, сутки)</b>')
        if fb_reach is not None:
            lines.append(f'• охват: {fb_reach}')
        if fb_eng is not None:
            lines.append(f'• вовлечённость: {fb_eng}')

    if ig_items:
        lines.append('\n<b>Instagram — топ постов</b>')
        for i, item in enumerate(ig_items, 1):
            head = html.escape((item['head'] or '(без подписи)')[:60])
            reach = item['reach'] if item['reach'] is not None else '—'
            lines.append(
                f'{i}. {head}\n   👁 {reach} · ❤️ {item["likes"]} · 💬 {item["comments"]}')

    if source_ranking:
        lines.append('\n<b>Источники по охвату (средн.)</b>')
        for i, (name, reach_avg, n) in enumerate(source_ranking, 1):
            lines.append(f'{i}. {html.escape(name)} — {round(reach_avg)} (n={n})')

    if hour_ranking:
        lines.append('\n<b>Лучшие часы по охвату (UTC, средн.)</b>')
        for i, (hour, reach_avg, n) in enumerate(hour_ranking, 1):
            lines.append(f'{i}. {int(hour):02d}:00 — {round(reach_avg)} (n={n})')

    if dow_hour_ranking:
        lines.append('\n<b>Лучшие слоты день×час (UTC, средн.)</b>')
        for i, (key, reward_avg, n) in enumerate(dow_hour_ranking, 1):
            lines.append(f'{i}. {_fmt_dow_hour(key)} — {round(reward_avg)} (n={n})')

    if format_ranking:
        lines.append('\n<b>Форматы по reward (средн.)</b>')
        for name, reward_avg, n in format_ranking:
            lines.append(f'• {html.escape(str(name))}: {round(reward_avg)} (n={n})')

    if variant_ranking:
        lines.append('\n<b>Хэштеги по reward (средн.)</b>')
        for name, reward_avg, n in variant_ranking:
            lines.append(f'• {html.escape(str(name))}: {round(reward_avg)} (n={n})')

    if len(lines) == 1:
        lines.append('\nданные недоступны (нет прав read_insights / instagram_manage_insights?)')

    return '\n'.join(lines)


async def report_insights(graph, telegram_bot_token, context, source_ranking=None, hour_ranking=None,
                          format_ranking=None, variant_ranking=None, dow_hour_ranking=None):
    ig_items = []
    fb_stats = {}
    ig_user_id = context.get('self_instagram_channel')
    if ig_user_id:
        try:
            ig_items = await asyncio.to_thread(
                get_instagram_media_insights,
                graph.access_token, ig_user_id, INSIGHTS_MEDIA_LIMIT, INSIGHTS_TOP_N)
        except Exception as e:
            logger.warning(f"[insights] IG media insights failed: {e}")
    try:
        fb_stats = await asyncio.to_thread(
            get_facebook_page_insights, graph.access_token, context['self_facebook_page_id'])
    except Exception as e:
        logger.warning(f"[insights] FB page insights failed: {e}")

    report = build_insights_report(
        ig_items, fb_stats, source_ranking, hour_ranking, format_ranking, variant_ranking,
        dow_hour_ranking)
    await send_message_api(report, telegram_bot_token, context)
    logger.info("[insights] report sent to debug chat")
