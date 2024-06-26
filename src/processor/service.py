import asyncio

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
from src.static.sources import translations


async def serve(client, graph, translator, translated_message, source, link, url_path):
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


def translate_message(translator, message_text, dest_lang):
    translated = translator.translate(message_text, dest=dest_lang)
    return translated.text
