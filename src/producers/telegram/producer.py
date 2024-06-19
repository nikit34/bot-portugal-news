import asyncio

from src.static.settings import MAX_LENGTH_MESSAGE, TIMEOUT, REPEAT_REQUESTS
from src.text_editor import trunc_str


def telegram_prepare_post(translated_message, source, link):
    title_post = '<a href="' + link + '">' + source + '</a>\n'
    return title_post + trunc_str(translated_message, MAX_LENGTH_MESSAGE)


async def telegram_send_message(client, telegram_chat_id, post, file, repeat=REPEAT_REQUESTS):
    try:
        return await client.send_message(
            entity=int(telegram_chat_id),
            message=post,
            file=file,
            parse_mode='html',
            link_preview=False
        )
    except Exception:
        if repeat > 0:
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            return await telegram_send_message(client, telegram_chat_id, post, file, repeat)


async def telegram_send_translated_respond(flag, message_sent, translated_text):
    await message_sent.respond(flag + ' ' + trunc_str(translated_text, MAX_LENGTH_MESSAGE), comment_to=message_sent.id)
