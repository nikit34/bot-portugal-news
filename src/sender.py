import asyncio

from src.history_comparator import is_duplicate_message
from src.static.settings import MAX_LENGTH_MESSAGE, TIMEOUT
from src.text_editor import trunc_str


async def process_and_send_message(client, translator, chat_id, posted_q, source, message_text, link, image):
    translated_message = _translate_message(translator, message_text, 'pt')

    if is_duplicate_message(translated_message, posted_q):
        return

    post = _prepare_post(translated_message, source, link)

    message_sent = await _send_message(client, chat_id, post, image, 5)
    if message_sent:
        await _send_translated_responses(translator, message_sent, translated_message)


def _translate_message(translator, message_text, dest_lang):
    translated = translator.translate(message_text, dest=dest_lang)
    return translated.text


def _prepare_post(translated_message, source, link):
    title_post = '<a href="' + link + '">' + source + '</a>\n'
    return title_post + trunc_str(translated_message, MAX_LENGTH_MESSAGE)


async def _send_message(client, chat_id, post, file, repeat):
    try:
        return await client.send_message(
            entity=int(chat_id),
            message=post,
            file=file,
            parse_mode='html',
            link_preview=False
        )
    except Exception:
        if repeat > 0:
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            await _send_message(client, chat_id, post, file, repeat)


async def _send_translated_responses(translator, message_sent, translated_message):
    translations = {'🇬🇧': 'en', '🇷🇺': 'ru'}
    for flag, lang in translations.items():
        translated_text = _translate_message(translator, translated_message, lang)
        await message_sent.respond(flag + ' ' + trunc_str(translated_text, MAX_LENGTH_MESSAGE), comment_to=message_sent.id)
