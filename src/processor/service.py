import asyncio
import os

from src.processor.history_comparator import is_duplicate_message
from src.producers.facebook.producer import (
    facebook_prepare_post,
    facebook_send_message,
    facebook_send_translated_respond
)
from src.producers.instagram.producer import (
    instagram_prepare_post,
    instagram_send_message,
    instagram_send_translated_respond
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

    if is_duplicate_message(translated_message, posted_q) or low_semantic_load(nlp, translated_message):
        return

    url_path = await handler()

    tasks = {}

    if platforms.get('telegram', False):
        telegram_post = telegram_prepare_post(translated_message, source, link)
        tasks['telegram'] = telegram_send_message(client, telegram_post, url_path)

    if platforms.get('facebook', False):
        facebook_post = facebook_prepare_post(translated_message, link)
        tasks['facebook'] = facebook_send_message(graph, facebook_post, url_path)

    if platforms.get('instagram', False):
        instagram_post = instagram_prepare_post(translated_message, link)
        tasks['instagram'] = instagram_send_message(graph, instagram_post, url_path)

    results = await asyncio.gather(*tasks.values())

    all_messages_sent = all(results)

    if all_messages_sent:
        translation_tasks = []

        for flag, lang in translations.items():
            translated_text = translate_message(translator, translated_message, lang)

            for platform, message_sent in zip(list(tasks.keys()), results):
                if platforms.get(platform, False):
                    if platform == 'telegram':
                        translation_tasks.append(
                            telegram_send_translated_respond(flag, message_sent, translated_text)
                        )
                    elif platform == 'facebook':
                        translation_tasks.append(
                            facebook_send_translated_respond(graph, flag, message_sent, translated_text)
                        )
                    elif platform == 'instagram':
                        translation_tasks.append(
                            instagram_send_translated_respond(graph, flag, message_sent, translated_text)
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
