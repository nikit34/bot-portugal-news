import asyncio
import os


from src.processor.history_comparator import is_ignored_prefix, is_duplicate_publish, get_decisions_publish_platforms
from src.processor.content_filter import is_blocked_content
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


# Shared per-run publish throttle: serialize publishing and cap posts per run
# to avoid bursts that trigger platform rate limits / spam bans.
_publish_lock = asyncio.Lock()
_published_count = 0


async def serve(client, graph, nlp, translator, message_text, handler_url_path, posted_d, context):
    global _published_count

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

    tasks = []

    if decisions_publish_platforms.get(Platform.FACEBOOK, False):
        if doc is None:
            doc = nlp(translated_message)
        facebook_post = facebook_prepare_post(translated_message, doc)
        tasks.append(facebook_send_message(graph, facebook_post, url_path, context))

    if decisions_publish_platforms.get(Platform.INSTAGRAM, False) and isinstance(url_path.get('url'), str):
        instagram_post = instagram_prepare_post(translated_message)
        tasks.append(instagram_send_message(graph, instagram_post, url_path, context))

    if decisions_publish_platforms.get(Platform.TELEGRAM, False):
        telegram_post = telegram_prepare_post(translated_message)
        tasks.append(telegram_send_message(client, telegram_post, url_path, context))

    if tasks:
        async with _publish_lock:
            if _published_count < MAX_POSTS_PER_RUN:
                _published_count += 1
                posted_d.get(Platform.ALL).appendleft(head)
                await asyncio.gather(*tasks)
                await asyncio.sleep(POST_DELAY_SECONDS)

    file_path = url_path.get('path')
    if file_path is not None and os.path.exists(file_path):
        os.remove(file_path)


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
