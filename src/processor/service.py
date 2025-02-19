import asyncio
import os
from functools import wraps

from src.processor.history_comparator import is_duplicate_message
from src.producers.facebook.producer import (
    facebook_prepare_post,
    facebook_send_message
)
from src.producers.instagram.producer import (
    instagram_prepare_post,
    instagram_send_message
)
from src.static.settings import MINIMUM_NUMBER_KEYWORDS, KEY_SEARCH_LENGTH_CHARS, MAX_VIDEO_SIZE_MB, TARGET_LANGUAGE
from src.static.sources import platforms


async def serve(graph, nlp, translator, message_text, handler, posted_q):
    translated_message = _translate_message(translator, message_text)

    cache_handler = _CacheHandler()
    cached_handler = cache_handler.cached(handler)

    head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()
    if is_duplicate_message(head, posted_q):
        return

    if _low_semantic_load(nlp, translated_message):
        url_path = await cached_handler()
        if not await _is_video(url_path):
            return
        elif _large_video_size(url_path):
            return

    posted_q.appendleft(head)

    url_path = await cached_handler()

    tasks = []

    if platforms.get('facebook', False):
        facebook_post = facebook_prepare_post(nlp, translated_message)
        tasks.append(facebook_send_message(graph, facebook_post, url_path))

    if platforms.get('instagram', False):
        instagram_post = instagram_prepare_post(translated_message)
        tasks.append(instagram_send_message(graph, instagram_post, url_path))

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
