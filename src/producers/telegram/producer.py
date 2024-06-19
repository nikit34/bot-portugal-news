import asyncio
import logging

from src.static.settings import TELEGRAM_MAX_LENGTH_MESSAGE, TIMEOUT, REPEAT_REQUESTS
from src.text_editor import trunc_str


logger = logging.getLogger(__name__)


def telegram_prepare_post(translated_message, source, link):
    title_post = '<a href="' + link + '">' + source + '</a>\n'
    return title_post + trunc_str(translated_message, TELEGRAM_MAX_LENGTH_MESSAGE)


async def telegram_send_message(client, telegram_chat_id, post, file, repeat=REPEAT_REQUESTS):
    try:
        return await client.send_message(
            entity=int(telegram_chat_id),
            message=post,
            file=file,
            parse_mode='html',
            link_preview=False
        )
    except Exception as e:
        if repeat > 0:
            logger.warning("Request 'telegram_send_message' failed, " + repeat + " times left: " + str(e))
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            return await telegram_send_message(client, telegram_chat_id, post, file, repeat)


async def telegram_send_translated_respond(flag, message_sent, translated_text, repeat=REPEAT_REQUESTS):
    try:
        await message_sent.respond(flag + ' ' + trunc_str(translated_text, TELEGRAM_MAX_LENGTH_MESSAGE), comment_to=message_sent.id)
    except Exception as e:
        if repeat > 0:
            logger.warning("Request 'telegram_send_translated_respond' failed, " + repeat + " times left: " + str(e))
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            await telegram_send_translated_respond(flag, message_sent, translated_text, repeat)