import asyncio
import logging
import os
import time


from src.processor.history_comparator import is_ignored_prefix, is_duplicate_publish, get_decisions_publish_platforms, make_head, mark_posted
from src.processor.content_filter import is_blocked_content, strip_promo
from src.processor.image_filter import is_unsafe_image
from src.producers.repeater import is_rate_limited
from src.producers.facebook.producer import (
    facebook_prepare_post,
    facebook_send_message
)
from src.producers.instagram.producer import (
    instagram_prepare_post,
    instagram_send_message
)
from src.producers.telegram.producer import (
    telegram_prepare_post,
    telegram_send_message
)
from src.static.settings import (
    MINIMUM_NUMBER_KEYWORDS,
    MAX_VIDEO_SIZE_MB,
    MAX_POSTS_PER_RUN,
    POST_DELAY_SECONDS,
    CONTENT_FILTER_ENABLED,
    IMAGE_NSFW_ENABLED,
)
from src.static.sources import Platform


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
# Effective cap for THIS run. Defaults to the static MAX_POSTS_PER_RUN; main may
# lower it for weak time slots when the optimal-time learning bias is enabled.
_run_cap = MAX_POSTS_PER_RUN


def set_run_cap(cap):
    global _run_cap
    _run_cap = cap


def budget_remaining():
    return _run_cap - _published_count


def get_publish_records():
    return _publish_records


async def serve(client, graph, nlp, translator, message_text, handler_url_path, posted_d, context, source=None):
    global _published_count, _meta_circuit_open

    translated_message = _translate_message(translator, message_text)

    if CONTENT_FILTER_ENABLED:
        translated_message = strip_promo(translated_message)

    head = make_head(translated_message)

    if is_ignored_prefix(head):
        return

    if CONTENT_FILTER_ENABLED and is_blocked_content(message_text, translated_message):
        return

    decisions_publish_platforms = get_decisions_publish_platforms(head, posted_d, context['platforms'])
    if is_duplicate_publish(decisions_publish_platforms):
        return

    if _published_count >= _run_cap:
        return

    url_path = await handler_url_path()
    is_video = _is_video(url_path)

    if not is_video and IMAGE_NSFW_ENABLED and is_unsafe_image(url_path.get('path')):
        return

    doc = None
    if not is_video:
        doc = nlp(translated_message)
        if _low_semantic_load(doc):
            return

    if is_video and _large_video_size(url_path):
        return

    targets = _targets_from_decisions(decisions_publish_platforms, url_path)

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
                # skip Meta targets while the circuit is open (don't hammer a rate-limited account)
                active = [
                    platform for platform in targets
                    if not (platform in (Platform.FACEBOOK, Platform.INSTAGRAM) and _meta_circuit_open)
                ]
                if active:
                    coros = []
                    for platform in active:
                        if platform is Platform.FACEBOOK:
                            if doc is None:
                                doc = nlp(translated_message)
                            coros.append(facebook_send_message(
                                graph, facebook_prepare_post(translated_message, doc), url_path, context))
                        elif platform is Platform.INSTAGRAM:
                            if doc is None:
                                doc = nlp(translated_message)
                            ig_caption, ig_comment = instagram_prepare_post(translated_message, doc)
                            coros.append(instagram_send_message(
                                graph, ig_caption, ig_comment, url_path, context))
                        else:
                            coros.append(telegram_send_message(
                                client, telegram_prepare_post(translated_message), url_path, context))

                    results = await asyncio.gather(*coros, return_exceptions=True)

                    succeeded = set()
                    for platform, result in zip(active, results):
                        if isinstance(result, Exception):
                            if platform in (Platform.FACEBOOK, Platform.INSTAGRAM) and is_rate_limited(result):
                                _meta_circuit_open = True
                                app_logger.warning(
                                    f"[serve] Meta rate limit on {platform.name}; pausing FB/IG for this run")
                            else:
                                app_logger.warning(f"[serve] {platform.name} publish failed: {result}")
                        else:
                            succeeded.add(platform)

                    if succeeded:
                        _published_count += 1
                        mark_posted(posted_d, head, succeeded)
                        if source:
                            _publish_records.append({'head': head, 'source': source, 'ts': time.time()})
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
    if decisions.get(Platform.TELEGRAM, False):
        targets.append(Platform.TELEGRAM)
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
