import asyncio
import logging
import os
import time
from collections import Counter


from src.files_manager import VideoSkip, SaveVideoUrl
from src.processor.history_comparator import is_ignored_prefix, is_duplicate_publish, get_decisions_publish_platforms, make_head, mark_posted
from src.processor.content_filter import is_blocked_content, strip_promo
from src.processor.topic_filter import is_off_topic
from src.processor.audience_filter import is_off_audience, has_portugal_signal
from src.utils.notify import redact_secrets
from src.processor.image_filter import is_unsafe_image, is_low_quality_image
from src.producers.repeater import is_rate_limited
from src.producers.facebook.producer import (
    facebook_prepare_post,
    facebook_send_message
)
from src.producers.instagram.producer import (
    instagram_prepare_post,
    instagram_send_message
)
from src.producers.media_uniquify import apply_uniquify
from src.producers.hashtags import extract_hashtags
from src.static.settings import (
    MINIMUM_NUMBER_KEYWORDS,
    MAX_VIDEO_SIZE_MB,
    MAX_POSTS_PER_RUN,
    POST_DELAY_SECONDS,
    CONTENT_FILTER_ENABLED,
    TOPIC_FILTER_ENABLED,
    AUDIENCE_FILTER_ENABLED,
    IMAGE_NSFW_ENABLED,
    IMAGE_QUALITY_FILTER_ENABLED,
    INSTAGRAM_DAILY_POST_LIMIT,
    UNIQUIFY_ENABLED,
    VARIANT_LOGGING_ENABLED,
    HASHTAG_MAX_FB,
    MAX_COUNT_KEYWORDS,
    CARDS_ENABLED,
    REEL_RENDER_ENABLED,
    STORY_GATE_ENABLED,
    STORY_GATE_IG_BUDGET_FRACTION,
    RANKER_ENABLED,
    RANKER_POOL_FACTOR,
    RANKER_SOURCE_SHARE,
    DIGEST_ITEMS,
    DIGEST_POOL_FACTOR,
    DIGEST_TITLE,
    DIGEST_TO_INSTAGRAM,
)
from src.producers.cards import build_card_image
from src.producers.reel import build_reel
from src.producers.digest_video import build_digest_video, build_digest_caption
from src.processor.ranker import candidate_score
from src.static.sources import Platform
from src.store import candidate_queue, dedup


app_logger = logging.getLogger('app')

# Shared per-run publish throttle: serialize publishing and cap posts per run
# to avoid bursts that trigger platform rate limits / spam bans.
_publish_lock = asyncio.Lock()
_published_count = 0
# Circuit breaker: once Meta (Facebook/Instagram) returns a rate limit, stop
# sending to it for the rest of the run instead of hammering it.
_meta_circuit_open = False
# Per-run attribution log: (head, source, ts) for posts published this run, so the
# learning loop can later tie each post's reach back to the source that produced it.
_publish_records = []
# How many top-of-pool candidates the ranker names in the log.
_LOG_TOP_N = 5

# Effective cap for THIS run. Defaults to the static MAX_POSTS_PER_RUN; main may
# lower it for weak time slots when the optimal-time learning bias is enabled.
_run_cap = MAX_POSTS_PER_RUN
# Daily Instagram post quota (UTC day), seeded by main from persisted state, so we
# stop publishing to IG before tripping Meta's ~25/24h limit (which would open the
# shared circuit and also block Facebook). _ig_daily_count is today's total so far.
_ig_daily_count = 0
_ig_daily_limit = INSTAGRAM_DAILY_POST_LIMIT
_ig_posts_this_run = 0
# Wall-clock deadline (time.monotonic()) after which parsers stop taking new work.
_deadline = None
# Seconds before _deadline at which phase-1 scraping must stop, leaving wall-clock
# headroom for the ranker's phase-2 drain (download+publish). 0 => no reserve.
_drain_reserve_seconds = 0
# Per-run telemetry for the debug-chat summary.
_platform_publishes = Counter()
# Candidate ranker (RANKER_ENABLED): phase-1 buffers candidates here; drain_pool
# scores them and publishes only the top ones. Capped so phase-1 stops scraping.
_candidate_pool = []
_pool_by_source = Counter()
# Режим дайджеста (main --mode digest): фаза 1 копит кандидатов ВСЕГДА, независимо
# от RANKER_ENABLED, а фаза 2 вместо N перепостов собирает один длинный ролик.
_digest_mode = False


def set_run_cap(cap):
    global _run_cap
    _run_cap = cap


def set_digest_mode(enabled):
    global _digest_mode
    _digest_mode = enabled


def set_ig_daily(count, limit):
    global _ig_daily_count, _ig_daily_limit
    _ig_daily_count = count
    _ig_daily_limit = limit


def set_deadline(monotonic_deadline):
    global _deadline
    _deadline = monotonic_deadline


def set_drain_reserve(seconds):
    global _drain_reserve_seconds
    _drain_reserve_seconds = seconds


def budget_remaining():
    return _run_cap - _published_count


def time_budget_exceeded():
    return _deadline is not None and time.monotonic() >= _deadline


def _scrape_budget_exceeded():
    # Phase-1 deadline: the full run deadline minus the drain reserve, so the ranker
    # always keeps wall-clock for phase 2. With no reserve this equals the deadline.
    return _deadline is not None and time.monotonic() >= (_deadline - _drain_reserve_seconds)


def _pool_target():
    # Сколько кандидатов имеет смысл накопить в фазе 1. В режиме дайджеста цель
    # задаётся числом сюжетов с запасом (часть отсеется на скачивании/фильтрах),
    # а не бюджетом постов — публикация там всего одна.
    if _digest_mode:
        return max(1, DIGEST_ITEMS * DIGEST_POOL_FACTOR)
    return max(1, _run_cap) * RANKER_POOL_FACTOR


def source_cap():
    """Потолок кандидатов от одного источника. 0 => без ограничения."""
    if RANKER_SOURCE_SHARE <= 0:
        return 0
    return max(1, int(_pool_target() * RANKER_SOURCE_SHARE))


def source_quota_filled(source):
    cap = source_cap()
    return bool(cap) and _pool_by_source[source] >= cap


def should_stop(source=None):
    # Parsers call this to stop taking new entries: either the per-run post budget
    # is filled, or the (reserve-adjusted) wall-clock budget is exhausted. With the
    # ranker on, also stop once the candidate pool is full — otherwise phase-1
    # (which never publishes) would scrape until the deadline.
    if (RANKER_ENABLED or _digest_mode) and source is not None \
            and source_quota_filled(source):
        return True
    if _digest_mode:
        return len(_candidate_pool) >= _pool_target() or _scrape_budget_exceeded()
    if RANKER_ENABLED and len(_candidate_pool) >= _pool_target():
        return True
    return budget_remaining() <= 0 or _scrape_budget_exceeded()


async def _load_queued_candidates(getter_client, context, posted_d):
    """Кандидаты, недобранные прошлыми прогонами: очередь переживает завершение job'а."""
    config_name = (context or {}).get('name')
    if not config_name or not candidate_queue.enabled():
        return []
    limit = _pool_target() - len(_candidate_pool)
    if limit <= 0:
        return []

    seen = {cand['head'] for cand in _candidate_pool}
    restored = []
    stale = []
    for payload in await candidate_queue.load(config_name, limit + len(seen)):
        head = payload.get('head')
        if not head or head in seen:
            continue
        if is_duplicate_publish(
                get_decisions_publish_platforms(head, posted_d, context['platforms'])):
            stale.append(payload['member'])
            continue
        handler = await candidate_queue.rehydrate_media(payload.get('media'), getter_client)
        if handler is None:
            stale.append(payload['member'])
            continue
        seen.add(head)
        restored.append({
            'head': head, 'source': payload.get('source'), 'text': payload.get('text') or '',
            'handler_url_path': handler, 'posted_d': posted_d, 'context': context,
            'is_video': bool(payload.get('is_video')), 'queue_member': payload['member'],
        })
        if len(restored) >= limit:
            break
    await candidate_queue.remove(config_name, stale)
    if restored:
        app_logger.info(f"[queue] restored {len(restored)} candidate(s) from Redis")
    return restored


async def drain_pool(graph, nlp, state, getter_client=None, context=None, posted_d=None):
    # Phase 2 of the ranker: score the buffered candidates and publish the best ones
    # first, until the per-run post budget or wall-clock deadline stops us. The
    # heavy work (download/NSFW/uniquify/publish) happens only for drained items.
    pool = list(_candidate_pool)
    if posted_d is None and pool:
        posted_d = pool[0]['posted_d']
    if context is None and pool:
        context = pool[0]['context']
    if posted_d is not None:
        pool.extend(await _load_queued_candidates(getter_client, context, posted_d))
    if not pool:
        return
    current_hour = time.gmtime().tm_hour
    scored = sorted(
        ((candidate_score(cand, state, current_hour), cand) for cand in pool),
        key=lambda pair: pair[0], reverse=True)
    ranked = [cand for _, cand in scored]
    app_logger.info(f"[ranker] draining {len(ranked)} pooled candidates by score")
    for position, (score, cand) in enumerate(scored[:_LOG_TOP_N], start=1):
        app_logger.info(
            f"[ranker] #{position} score={score:.2f} "
            f"pt={int(has_portugal_signal(cand['head'], cand['text']))} "
            f"video={int(bool(cand.get('is_video')))} {cand['source']} | {cand['head']}")
    consumed = []
    try:
        for cand in ranked:
            # Drain uses the FULL run deadline (not the reserve-adjusted scrape stop)
            # so the headroom reserved away from phase 1 is actually spent publishing.
            if budget_remaining() <= 0 or time_budget_exceeded():
                break
            await _download_and_publish(
                graph, nlp, cand['text'], cand['handler_url_path'],
                cand['posted_d'], cand['context'], cand['source'], cand['head'])
            consumed.append(cand.get('queue_member'))
    finally:
        _candidate_pool.clear()
        _pool_by_source.clear()
        await candidate_queue.remove((context or {}).get('name'), consumed)


async def drain_digest(graph, nlp, state, context):
    # Фаза 2 в режиме ДАЙДЖЕСТА: вместо N отдельных перепостов собираем из лучших
    # кандидатов один длинный озвученный ролик и публикуем его ОДИН раз.
    #
    # Экономический смысл — в digest_video.py: длинное видео платит в 10-50 раз
    # больше за просмотр, копит минуты просмотра (по ним считается допуск в
    # монетизацию) и оригинально по построению, т.е. выводит страницу из-под
    # «aggregating/duplicative content».
    #
    # Берём только ФОТО-кандидатов: сегмент собирается из статичного кадра с нашей
    # плашкой, чужой видеоклип внутрь не вставляем (это вернуло бы неоригинальность).
    if not _candidate_pool:
        app_logger.info("[digest] candidate pool empty; nothing to assemble")
        return
    current_hour = time.gmtime().tm_hour
    ranked = sorted(_candidate_pool, key=lambda c: candidate_score(c, state, current_hour),
                    reverse=True)
    app_logger.info(f"[digest] assembling from {len(ranked)} pooled candidates")

    items = []
    used = []
    try:
        for cand in ranked:
            if len(items) >= DIGEST_ITEMS or time_budget_exceeded():
                break
            if cand.get('is_video'):
                continue
            prepared = await _download_and_filter(
                cand['handler_url_path'], nlp, cand['text'], cand['source'], cand['head'])
            if prepared is None:
                continue
            url_path, is_video, _doc = prepared
            if is_video:
                # Пост-фактум оказался видео (hint соврал) — в дайджест не берём,
                # но и не публикуем отдельно: это работа обычного прогона.
                continue
            items.append({'path': url_path.get('path'), 'text': cand['text']})
            used.append(cand)

        video_path, headlines = await asyncio.to_thread(build_digest_video, items)
        if not video_path:
            return

        title = DIGEST_TITLE % time.strftime('%d.%m.%Y', time.gmtime())
        caption = build_digest_caption(title, headlines)
        await _publish_digest(graph, context, video_path, caption, used, title)
    finally:
        for item in items:
            path = item.get('path')
            if path and os.path.exists(path):
                os.remove(path)
        _candidate_pool.clear()
        _pool_by_source.clear()


async def _publish_digest(graph, context, video_path, caption, used, head):
    # Публикация готового ролика. Facebook — цель (там деньги), Telegram — витрина.
    # Instagram по умолчанию выключен: за просмотры он почти не платит, а публикация
    # всё равно съест суточную квоту IG.
    global _published_count, _meta_circuit_open, _ig_daily_count, _ig_posts_this_run

    url_path = {'path': video_path, 'url': None}
    posted_d = used[0]['posted_d'] if used else {}

    async with _publish_lock:
        targets = [Platform.FACEBOOK] if Platform.FACEBOOK in context['platforms'] else []
        if DIGEST_TO_INSTAGRAM and Platform.INSTAGRAM in context['platforms'] \
                and _ig_daily_count < _ig_daily_limit:
            targets.append(Platform.INSTAGRAM)
        if _meta_circuit_open:
            targets = [t for t in targets if t not in (Platform.FACEBOOK, Platform.INSTAGRAM)]
        if not targets:
            app_logger.warning("[digest] no publish targets; skipping")
            return

        coros = []
        for platform in targets:
            if platform is Platform.FACEBOOK:
                # publish_story=False: дублировать многоминутный ролик в сторис
                # бессмысленно (сторис живут 24ч и не доходят до не-подписчиков).
                coros.append(facebook_send_message(
                    graph, caption, url_path, context, publish_story=False))
            elif platform is Platform.INSTAGRAM:
                coros.append(instagram_send_message(
                    graph, caption, None, url_path, context, publish_story=False))

        results = await asyncio.gather(*coros, return_exceptions=True)

        succeeded = set()
        fb_post_id = None
        fb_media_id = None
        ig_media_id = None
        for platform, result in zip(targets, results):
            if isinstance(result, Exception):
                if platform in (Platform.FACEBOOK, Platform.INSTAGRAM) and is_rate_limited(result):
                    _meta_circuit_open = True
                app_logger.warning(
                    f"[digest] {platform.name} publish failed: {redact_secrets(str(result))}")
                continue
            succeeded.add(platform)
            _platform_publishes[platform.name] += 1
            if platform is Platform.FACEBOOK and isinstance(result, dict):
                fb_post_id = result.get('post_id') or result.get('id')
                fb_media_id = result.get('id')
            if platform is Platform.INSTAGRAM:
                _ig_daily_count += 1
                _ig_posts_this_run += 1
                if isinstance(result, dict):
                    ig_media_id = result.get('id')

        if not succeeded:
            return
        _published_count += 1
        mark_posted(posted_d, head, succeeded)
        await dedup.record(context.get('name'), head, succeeded)
        for cand in used:
            # Сюжеты, ушедшие в ролик, помечаем использованными, чтобы в этом же
            # прогоне они не разошлись ещё и отдельными постами.
            mark_posted(cand['posted_d'], cand['head'], succeeded)
            await dedup.record(context.get('name'), cand['head'], succeeded)
        # is_digest уводит reward дайджеста в СВОЙ бакет: его величина (минуты
        # просмотра длинного ролика) на порядок больше пост-уровня и, попав в
        # sources/hours, перекосила бы нормировку ранкера и бюджет часов.
        _publish_records.append({
            'head': head, 'source': 'digest', 'ts': time.time(), 'is_video': True,
            'is_digest': True, 'fb_id': fb_post_id, 'fb_media_id': fb_media_id,
            'ig_id': ig_media_id})
        app_logger.info(f"[digest] published to {[p.name for p in succeeded]}")


def get_publish_records():
    return _publish_records


def ig_posts_this_run():
    return _ig_posts_this_run


def get_run_stats():
    return {
        'posts': _published_count,
        'platforms': dict(_platform_publishes),
        'ig_today': _ig_daily_count,
        'ig_limit': _ig_daily_limit,
        'ig_this_run': _ig_posts_this_run,
        'meta_circuit_open': _meta_circuit_open,
    }


async def serve(graph, nlp, translator, message_text, handler_url_path, posted_d,
                context, source=None, is_video_hint=False, recipe_checked=False):
    # Phase-1 intake: cheap text-only filters + dedup + budget check. With the ranker
    # OFF (default) we publish inline immediately (unchanged FIFO behavior); with it
    # ON we pool the candidate and defer the expensive download/publish to drain_pool.

    # Гейт recipe_only живёт на границе публикации, а не только в парсерах: в канал по
    # кухне (FB+IG) уходит лишь то, что источник ЯВНО пометил проверенным на рецепт
    # (recipe_checked, см. recipe_filter.is_recipe). Fail-closed: путь, который гейт не
    # прогнал, не опубликует ничего вместо того, чтобы протащить не-рецепт.
    if context.get('recipe_only') and not recipe_checked:
        app_logger.warning(
            f"[serve] recipe_only config: dropping post from {source} - recipe gate was not applied")
        return

    if source in context.get('native_language_sources', ()):
        translated_message = message_text
    else:
        translated_message = _translate_message(translator, message_text)

    if CONTENT_FILTER_ENABLED:
        translated_message = strip_promo(translated_message)

    head = make_head(translated_message)

    if is_ignored_prefix(head):
        return

    if CONTENT_FILTER_ENABLED and is_blocked_content(message_text, translated_message):
        return

    if TOPIC_FILTER_ENABLED and is_off_topic(message_text, translated_message):
        return

    if AUDIENCE_FILTER_ENABLED and is_off_audience(message_text, translated_message):
        return

    decisions_publish_platforms = get_decisions_publish_platforms(head, posted_d, context['platforms'])
    if is_duplicate_publish(decisions_publish_platforms):
        return

    if _published_count >= _run_cap:
        return

    # Video-ness known BEFORE download: RSS direct-video by handler type, Telegram by
    # the hint the parser derives from telethon metadata. The hint is gated to media
    # telethon saves as .mp4 — the SAME thing phase-2's _is_video recognises — so a
    # candidate flagged here is guaranteed to still be video after download (phase-1
    # and phase-2 agree), never re-classified as a photo.
    likely_video = is_video_hint or isinstance(handler_url_path, SaveVideoUrl)

    # Text-quality gate at phase-1 (previously phase-2 only): drop posts with too
    # little text BEFORE they take a ranker pool slot. Otherwise a high-reward source
    # of headline/emoji-only posts (e.g. some Telegram channels) fills the pool with
    # candidates that phase-2 rejects, and should_stop() halts scraping before any
    # text-rich source (RSS) is reached — starving the whole run to zero posts.
    # Video is exempt: its value is the clip, not the caption, and phase-2 never
    # rejects a real .mp4 on semantic load — so pooling a short-caption video still
    # publishes it (no phase-2 rejection => no starvation), unlike a short-caption photo.
    if not likely_video and _low_semantic_load(nlp(translated_message)):
        app_logger.debug(f"[serve] skipping low-semantic-load post from {source}: head={head!r}")
        return

    if RANKER_ENABLED or _digest_mode:
        if len(_candidate_pool) < _pool_target() and not source_quota_filled(source):
            candidate = {
                'head': head, 'source': source, 'text': translated_message,
                'handler_url_path': handler_url_path, 'posted_d': posted_d, 'context': context,
                'is_video': likely_video,
            }
            _candidate_pool.append(candidate)
            _pool_by_source[source] += 1
            if not _digest_mode:
                candidate['queue_member'] = await candidate_queue.push(
                    context.get('name'), candidate)
        return

    await _download_and_publish(
        graph, nlp, translated_message, handler_url_path, posted_d, context, source, head)


async def _download_and_filter(handler_url_path, nlp, translated_message, source, head):
    # Скачивание медиа + все медиа-фильтры. Выделено из _download_and_publish, чтобы
    # дайджест-ролик (drain_digest) собирал сюжеты по ТЕМ ЖЕ правилам качества, что и
    # обычная публикация, без дублирования логики. Возвращает (url_path, is_video, doc)
    # или None, если запись отсеяна.
    try:
        url_path = await handler_url_path()
    except VideoSkip as e:
        # Видео сознательно пропущено загрузчиком (длинное/большое/недоступный
        # формат) — это не сбой, просто не постим эту запись.
        app_logger.debug(f"[serve] video skipped from {source}: {e}")
        return None

    if not url_path or not url_path.get('path'):
        # Загрузчик не вернул локальный файл — например, Telegram-медиа без
        # скачиваемого файла (poll/geo/contact/dice): download_media отдаёт None.
        # Постить нечего и все нижележащие фильтры ждут путь к файлу — пропускаем.
        app_logger.debug(f"[serve] no media file downloaded from {source}; skipping")
        return None

    is_video = _is_video(url_path)

    if not is_video and IMAGE_QUALITY_FILTER_ENABLED and is_low_quality_image(url_path.get('path')):
        app_logger.debug(f"[serve] skipping low-quality image from {source}")
        return None

    if not is_video and IMAGE_NSFW_ENABLED and await asyncio.to_thread(is_unsafe_image, url_path.get('path')):
        app_logger.debug(f"[serve] skipping NSFW image from {source}")
        return None

    doc = None
    if not is_video:
        doc = nlp(translated_message)
        if _low_semantic_load(doc):
            app_logger.debug(f"[serve] skipping low-semantic-load post from {source}: head={head!r}")
            return None

    if is_video and _large_video_size(url_path):
        app_logger.debug(f"[serve] skipping oversized video from {source}")
        return None

    return url_path, is_video, doc


async def _download_and_publish(graph, nlp, translated_message, handler_url_path,
                                posted_d, context, source, head):
    # Phase-2 core: download media, run media filters, build the original card,
    # uniquify, then publish under the lock. Shared by the inline path (ranker off)
    # and drain_pool (ranker on) so the publish/dedup/throttle logic lives in one place.
    global _published_count, _meta_circuit_open, _ig_daily_count, _ig_posts_this_run

    prepared = await _download_and_filter(handler_url_path, nlp, translated_message, source, head)
    if prepared is None:
        return
    url_path, is_video, doc = prepared

    # narrated-Reel: картинку/текст-новость превращаем в вертикальное видео с нашей
    # плашкой-заголовком и TTS-озвучкой — контент оригинален ПО ПОСТРОЕНИЮ (заменяет
    # watermark/uniquify для этого поста и проходит фильтр оригинальности Meta 2026).
    # Успех => дальше пост идёт по видео-пути публикации (Reels). Fail-open: нет
    # piper/голоса/ffmpeg или любой сбой => reel None, продолжаем как раньше.
    reel_made = False
    if REEL_RENDER_ENABLED and not is_video:
        reel_path = await asyncio.to_thread(build_reel, url_path.get('path'), translated_message)
        if reel_path:
            original = url_path.get('path')
            url_path['path'] = reel_path
            url_path['url'] = None
            if original and original != reel_path and os.path.exists(original):
                os.remove(original)
            is_video = True
            reel_made = True

    # Карточка оригинальной графики (трансфер/сумма) как нативное фото — добавленная
    # ценность против unoriginal-content демоута. Подменяем медиа на нашу карточку
    # ДО уникализации; ошибка/неподходящая новость => публикуем оригинал (fail-open).
    if CARDS_ENABLED and not is_video:
        card_path = await asyncio.to_thread(
            build_card_image, url_path.get('path'), translated_message, doc)
        if card_path:
            original = url_path.get('path')
            url_path['path'] = card_path
            url_path['url'] = None  # IG чеканит из локального файла, а не из ссылки источника
            if original and original != card_path and os.path.exists(original):
                os.remove(original)

    # Уникализируем + брендируем медиа ПОСЛЕ всех фильтров (фильтры смотрят оригинал)
    # и ДО публикации. Мутирует url_path: подменяет локальный файл и обнуляет 'url',
    # чтобы IG тоже постил обработанный файл, а не оригинальную ссылку источника.
    # reel_made => пропускаем: narrated-Reel уже оригинал по построению, watermark/
    # uniquify только повредили бы (лишний ре-энкод + сигнал неоригинальности).
    if UNIQUIFY_ENABLED and not reel_made:
        await asyncio.to_thread(apply_uniquify, url_path, is_video, context)

    decisions_publish_platforms = get_decisions_publish_platforms(head, posted_d, context['platforms'])
    targets = _targets_from_decisions(decisions_publish_platforms, url_path)
    # Diagnostic: publish gate is otherwise fully silent. Log why a pooled candidate
    # does/doesn't publish so a "no posts" stall can't hide (decisions vs targets).
    app_logger.info(
        f"[serve] publish-gate {source}: head={head!r} decisions="
        f"{ {p.name: v for p, v in decisions_publish_platforms.items()} } "
        f"targets={[t.name for t in targets]} published={_published_count}/{_run_cap} "
        f"ig={_ig_daily_count}/{_ig_daily_limit} circuit={_meta_circuit_open}")

    if targets:
        async with _publish_lock:
            # Re-derive the decision under the lock. The dedup check above runs
            # unlocked while media download / NSFW / NLP happen, so two parallel
            # serve() calls for the same story (split across chunks or sources)
            # can both pass it and both publish. Re-checking here — after any
            # concurrent mark_posted — keeps check-and-publish atomic and stops
            # the same post going out twice in one run.
            decisions_publish_platforms = get_decisions_publish_platforms(
                head, posted_d, context['platforms'])
            targets = _targets_from_decisions(decisions_publish_platforms, url_path)

            if targets and _published_count < _run_cap:
                if Platform.INSTAGRAM in targets and _ig_daily_count >= _ig_daily_limit:
                    app_logger.info(
                        f"[serve] IG daily quota reached ({_ig_daily_count}/{_ig_daily_limit}); skipping IG")
                # skip Meta targets while the circuit is open (don't hammer a rate-limited
                # account), and skip IG once its daily quota is spent
                active = [
                    platform for platform in targets
                    if not (platform in (Platform.FACEBOOK, Platform.INSTAGRAM) and _meta_circuit_open)
                    and not (platform is Platform.INSTAGRAM and _ig_daily_count >= _ig_daily_limit)
                ]
                if active:
                    # Story-gate: when enabled, suppress the extra Story mirror once the
                    # IG daily budget is tight (Stories don't reach non-followers and each
                    # one burns a slot). Off by default => always mirror (current behavior).
                    publish_story = True
                    if STORY_GATE_ENABLED:
                        publish_story = _ig_daily_count < STORY_GATE_IG_BUDGET_FRACTION * _ig_daily_limit
                    coros = []
                    for platform in active:
                        if platform is Platform.FACEBOOK:
                            if doc is None:
                                doc = nlp(translated_message)
                            coros.append(facebook_send_message(
                                graph, facebook_prepare_post(translated_message, doc), url_path, context,
                                publish_story=publish_story))
                        elif platform is Platform.INSTAGRAM:
                            if doc is None:
                                doc = nlp(translated_message)
                            ig_caption, ig_comment = instagram_prepare_post(translated_message, doc)
                            coros.append(instagram_send_message(
                                graph, ig_caption, ig_comment, url_path, context,
                                publish_story=publish_story))

                    results = await asyncio.gather(*coros, return_exceptions=True)

                    succeeded = set()
                    fb_post_id = None
                    fb_media_id = None
                    ig_media_id = None
                    for platform, result in zip(active, results):
                        if isinstance(result, Exception):
                            if platform in (Platform.FACEBOOK, Platform.INSTAGRAM) and is_rate_limited(result):
                                _meta_circuit_open = True
                                app_logger.warning(
                                    f"[serve] Meta rate limit on {platform.name}; pausing FB/IG for this run")
                            else:
                                app_logger.warning(
                                    f"[serve] {platform.name} publish failed: {redact_secrets(str(result))}")
                        else:
                            succeeded.add(platform)
                            _platform_publishes[platform.name] += 1
                            # Capture publish IDs for precise per-post attribution later.
                            # FB feed photo carries a page-post id ('post_id'); /videos
                            # returns only 'id'. Insights need the page-post id.
                            if platform is Platform.FACEBOOK and isinstance(result, dict):
                                fb_post_id = result.get('post_id') or result.get('id')
                                # Отдельно media-id: время просмотра живёт на
                                # /{video-id}/video_insights, а не на story-узле поста.
                                fb_media_id = result.get('id')
                            if platform is Platform.INSTAGRAM:
                                _ig_daily_count += 1
                                _ig_posts_this_run += 1
                                if isinstance(result, dict):
                                    ig_media_id = result.get('id')

                    if succeeded:
                        _published_count += 1
                        mark_posted(posted_d, head, succeeded)
                        await dedup.record(context.get('name'), head, succeeded)
                        if source:
                            record = {'head': head, 'source': source, 'ts': time.time(),
                                      'is_video': is_video, 'fb_id': fb_post_id,
                                      'fb_media_id': fb_media_id, 'ig_id': ig_media_id}
                            if VARIANT_LOGGING_ENABLED and doc is not None:
                                max_tags = (HASHTAG_MAX_FB if Platform.FACEBOOK in succeeded
                                            else MAX_COUNT_KEYWORDS)
                                record['hashtag_n'] = len(extract_hashtags(doc, max_tags))
                            _publish_records.append(record)
                        await asyncio.sleep(POST_DELAY_SECONDS)

    file_path = url_path.get('path')
    if file_path is not None and os.path.exists(file_path):
        os.remove(file_path)


def _targets_from_decisions(decisions, url_path):
    targets = []
    if decisions.get(Platform.FACEBOOK, False):
        targets.append(Platform.FACEBOOK)
    if decisions.get(Platform.INSTAGRAM, False) and _instagram_publishable(url_path):
        targets.append(Platform.INSTAGRAM)
    return targets


def _instagram_publishable(url_path):
    # Видео идёт как Reel через resumable upload локального .mp4. Фото — по
    # публичному image_url: если он есть (RSS), берём как есть; если нет (фото из
    # Telegram), URL чеканится через FB CDN из локального файла. Значит для IG
    # достаточно иметь скачанный локальный файл.
    return bool(url_path.get('path'))


def _translate_message(translator, message_text):
    # deep-translator returns None for untranslatable input (e.g. emoji-only);
    # fall back to '' so it gets filtered out instead of crashing serve()
    return translator.translate(message_text) or ''


def _low_semantic_load(doc):
    keywords = [token.text for token in doc if not token.is_stop and not token.is_punct]
    return len(keywords) < MINIMUM_NUMBER_KEYWORDS


def _is_video(url_path):
    return url_path.get('path').lower().endswith('.mp4')


def _large_video_size(url_path):
    file_path = url_path.get('path')
    size = os.path.getsize(file_path)
    size_mb = size / (1024 * 1024)
    return size_mb > MAX_VIDEO_SIZE_MB
