import asyncio
import logging
import os


from src.processor.history_comparator import is_ignored_prefix, is_duplicate_publish, get_decisions_publish_platforms
from src.processor.content_filter import is_blocked_content
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
    KEY_SEARCH_LENGTH_CHARS,
    MAX_VIDEO_SIZE_MB,
    TARGET_LANGUAGE,
    MAX_POSTS_PER_RUN,
    POST_DELAY_SECONDS,
    CONTENT_FILTER_ENABLED,
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


async def serve(client, graph, nlp, translator, message_text, handler_url_path, posted_d, context):
    global _published_count, _meta_circuit_open

    translated_message = _translate_message(translator, message_text)

    head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()

    if is_ignored_prefix(head):
        return

    if CONTENT_FILTER_ENABLED and is_blocked_content(message_text, translated_message):
        return

    decisions_publish_platforms = get_decisions_publish_platforms(head, posted_d, context['platforms'])
    if is_duplicate_publish(decisions_publish_platforms):
        return

    if _published_count >= MAX_POSTS_PER_RUN:
        return

    url_path = await handler_url_path()
    is_video = _is_video(url_path)

    doc = None
    if not is_video:
        doc = nlp(translated_message)
        if _low_semantic_load(doc):
            return

    if is_video and _large_video_size(url_path):
        return

    targets = []
    if decisions_publish_platforms.get(Platform.FACEBOOK, False):
        targets.append(Platform.FACEBOOK)
    if decisions_publish_platforms.get(Platform.INSTAGRAM, False) and isinstance(url_path.get('url'), str):
        targets.append(Platform.INSTAGRAM)
    if decisions_publish_platforms.get(Platform.TELEGRAM, False):
        targets.append(Platform.TELEGRAM)

    if targets:
        async with _publish_lock:
            if _published_count < MAX_POSTS_PER_RUN:
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
                            coros.append(instagram_send_message(
                                graph, instagram_prepare_post(translated_message), url_path, context))
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
                        _mark_posted(posted_d, head, decisions_publish_platforms, context['platforms'], succeeded)
                        await asyncio.sleep(POST_DELAY_SECONDS)

    file_path = url_path.get('path')
    if file_path is not None and os.path.exists(file_path):
        os.remove(file_path)


def _mark_posted(posted_d, head, decisions, platforms, succeeded):
    # Record where the post now lives so a failed platform retries next run
    # instead of being marked done. Deques are mutually exclusive:
    # ALL = on both FB and TG, TELEGRAM = TG only, FACEBOOK = FB only.
    def located(platform):
        if platform in succeeded:
            return True
        # decision False while the platform is enabled => it was already there (dup)
        return not decisions.get(platform, False) and bool(platforms.get(platform))

    on_facebook = located(Platform.FACEBOOK)
    on_telegram = located(Platform.TELEGRAM)

    if on_facebook and on_telegram:
        posted_d.get(Platform.ALL).appendleft(head)
    elif on_telegram:
        posted_d.get(Platform.TELEGRAM).appendleft(head)
    elif on_facebook:
        posted_d.get(Platform.FACEBOOK).appendleft(head)


def _translate_message(translator, message_text):
    translated = translator.translate(message_text, dest=TARGET_LANGUAGE)
    return translated.text


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
