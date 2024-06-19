from src.history_comparator import is_duplicate_message
from src.producers.facebook.producer import (
    facebook_prepare_post,
    facebook_send_message,
    facebook_send_translated_respond
)
from src.producers.telegram.producer import (
    telegram_send_translated_respond,
    telegram_send_message,
    telegram_prepare_post
)


async def send_message(client, graph, translator, telegram_chat_id, posted_q, source, message_text, link, image):
    translated_message = translate_message(translator, message_text, 'pt')

    if is_duplicate_message(translated_message, posted_q):
        return

    telegram_post = telegram_prepare_post(translated_message, source, link)
    facebook_post = facebook_prepare_post(translated_message, link)

    telegram_message_sent = await telegram_send_message(client, telegram_chat_id, telegram_post, image)
    facebook_message_sent = await facebook_send_message(graph, facebook_post, image)
    if telegram_message_sent:
        translations = {'🇬🇧': 'en', '🇷🇺': 'ru'}
        for flag, lang in translations.items():
            translated_text = translate_message(translator, translated_message, lang)
            await telegram_send_translated_respond(flag, telegram_message_sent, translated_text)
            await facebook_send_translated_respond(graph, flag, facebook_message_sent, translated_text)


def translate_message(translator, message_text, dest_lang):
    translated = translator.translate(message_text, dest=dest_lang)
    return translated.text
