import asyncio
import os
from functools import wraps


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
    translated_message = _translate_message(translator, message_text)

    cache_handler = _CacheHandler()
    cached_handler_url_path = cache_handler.cached(handler_url_path)

    head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()
    
    if is_ignored_prefix(head):
        return

    decisions_publish_platforms = get_decisions_publish_platforms(head, posted_d, context['platforms']) 
    if is_duplicate_publish(decisions_publish_platforms):
        return

    url_path = await cached_handler_url_path()
    is_video = await _is_video(url_path)
    
    if not is_video and _low_semantic_load(nlp, translated_message):
        return
    
    if is_video and _large_video_size(url_path):
        return

    posted_d.get(Platform.ALL).appendleft(head)

    tasks = []

    if decisions_publish_platforms.get(Platform.FACEBOOK, False):
        facebook_post = facebook_prepare_post(nlp, translated_message)
        tasks.append(facebook_send_message(graph, facebook_post, url_path, context))

    if decisions_publish_platforms.get(Platform.INSTAGRAM, False):
        instagram_post = instagram_prepare_post(translated_message)
        tasks.append(instagram_send_message(graph, instagram_post, url_path, context))

    if decisions_publish_platforms.get(Platform.TELEGRAM, False):
        telegram_post = telegram_prepare_post(translated_message)
        tasks.append(telegram_send_message(client, telegram_post, url_path))

    await asyncio.gather(*tasks)

    file_path = url_path.get('path')
    if file_path is not None:
        os.remove(file_path)


def _translate_message(translator, message_text):
    translated = translator.translate(message_text, dest=TARGET_LANGUAGE)
    return translated.text


def _extract_keywords(nlp, text):
    doc = nlp(text)
    keywords = [token.text for token in doc if token.is_stop != True and token.is_punct != True]
    return keywords


def _low_semantic_load(nlp, message):
    keywords = _extract_keywords(nlp, message)
    return len(keywords) < MINIMUM_NUMBER_KEYWORDS


class _CacheHandler:
    def __init__(self):
        self.cache = None

    def cached(self, func):
        @wraps(func)
        async def wrapper():
            if self.cache is None:
                self.cache = await func()
            return self.cache
        return wrapper


async def _is_video(url_path):
    return url_path.get('path').lower().endswith('.mp4')


def _large_video_size(url_path):
    file_path = url_path.get('path')
    size = os.path.getsize(file_path)
    size_mb = size / (1024 * 1024)
    return size_mb > MAX_VIDEO_SIZE_MB
