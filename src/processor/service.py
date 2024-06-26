import asyncio
import os

from src.files_manager import save_file_tmp_from_url, save_file_tmp_from_telegram
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
from src.static.sources import translations


async def serve(client, graph, nlp, translator, message_text, source, link, image, posted_q):
    translated_message = translate_message(translator, message_text, 'pt')

    if is_duplicate_message(translated_message, posted_q) or low_semantic_load(nlp, translated_message):
        return

    if isinstance(image, str):
        url_path = await save_file_tmp_from_url(image)
    else:
        url_path = await save_file_tmp_from_telegram(client, image)

    telegram_post = telegram_prepare_post(translated_message, source, link)
    facebook_post = facebook_prepare_post(translated_message, link)
    instagram_post = instagram_prepare_post(translated_message, link)

    telegram_task = telegram_send_message(client, telegram_post, url_path)
    facebook_task = facebook_send_message(graph, facebook_post, url_path)
    instagram_task = instagram_send_message(graph, instagram_post, url_path)

    telegram_message_sent, facebook_message_sent, instagram_message_sent = await asyncio.gather(
        telegram_task, facebook_task, instagram_task
    )
    if telegram_message_sent and facebook_message_sent and instagram_message_sent:
        translation_tasks = []

        for flag, lang in translations.items():
            translated_text = translate_message(translator, translated_message, lang)
            translation_tasks.append(
                telegram_send_translated_respond(flag, telegram_message_sent, translated_text)
            )
            translation_tasks.append(
                facebook_send_translated_respond(graph, flag, facebook_message_sent, translated_text)
            )
            translation_tasks.append(
                instagram_send_translated_respond(graph, flag, instagram_message_sent, translated_text)
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

