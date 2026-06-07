import asyncio
import os


from src.processor.history_comparator import is_ignored_prefix, is_duplicate_publish, get_decisions_publish_platforms
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
from src.static.settings import MINIMUM_NUMBER_KEYWORDS, KEY_SEARCH_LENGTH_CHARS, MAX_VIDEO_SIZE_MB, TARGET_LANGUAGE
from src.static.sources import Platform


async def serve(client, graph, nlp, translator, message_text, handler_url_path, posted_d, context):
    translated_message = await asyncio.to_thread(_translate_message, translator, message_text)

    head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()

    if is_ignored_prefix(head):
        return

    decisions_publish_platforms = get_decisions_publish_platforms(head, posted_d, context['platforms'])
    if is_duplicate_publish(decisions_publish_platforms):
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

    posted_d.get(Platform.ALL).appendleft(head)

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

    await asyncio.gather(*tasks)

    file_path = url_path.get('path')
    if file_path is not None:
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
