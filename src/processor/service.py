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
from src.producers.telegram.producer import (
    telegram_send_translated_respond,
    telegram_send_message,
    telegram_prepare_post
)
from src.static.settings import MINIMUM_NUMBER_KEYWORDS
from src.static.sources import translations, platforms


async def serve(client, graph, nlp, translator, message_text, source, link, handler, posted_q):
    translated_message = translate_message(translator, message_text, 'pt')

    if is_duplicate_message(translated_message, posted_q):
        return

    cache_handler = CacheHandler()
    cached_handler = cache_handler.cached(handler)

    if low_semantic_load(nlp, translated_message):
        url_path = await cached_handler()
        if not await is_video(url_path):
            return

    url_path = await cached_handler()

    tasks = []
    telegram_post = telegram_prepare_post(translated_message, source, link)
    tasks.append(telegram_send_message(client, telegram_post, url_path))

    if platforms.get('facebook', False):
        facebook_post = facebook_prepare_post(translated_message, link)
        tasks.append(facebook_send_message(graph, facebook_post, url_path))

    if platforms.get('instagram', False):
        instagram_post = instagram_prepare_post(translated_message, link)
        tasks.append(instagram_send_message(graph, instagram_post, url_path))

    results = await asyncio.gather(*tasks)

    telegram_messages_sent = results[0]

    if telegram_messages_sent:
        translation_tasks = []

        for flag, lang in translations.items():
            translated_text = translate_message(translator, translated_message, lang)
            translation_tasks.append(
                telegram_send_translated_respond(flag, telegram_messages_sent, translated_text)
            )

        await asyncio.gather(*translation_tasks)

    file_path = url_path.get('path')
    if file_path is not None:
        os.remove(file_path)


def translate_message(translator, message_text, dest_lang):
    translated = translator.translate(message_text, dest=dest_lang)
    return translated.text


def _extract_keywords(nlp, text):
    doc = nlp(text)
    keywords = [token.text for token in doc if token.is_stop != True and token.is_punct != True]
    return keywords


def low_semantic_load(nlp, message):
    keywords = _extract_keywords(nlp, message)
    return len(keywords) < MINIMUM_NUMBER_KEYWORDS


class CacheHandler:
    def __init__(self):
        self.cache = None

    def cached(self, func):
        @wraps(func)
        async def wrapper():
            if self.cache is None:
                self.cache = await func()
            return self.cache
        return wrapper


async def is_video(url_path):
    return url_path.get('path').lower().endswith('.mp4')
