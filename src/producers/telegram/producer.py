from src.producers.repeater import async_retry
from src.static.settings import TELEGRAM_MAX_LENGTH_MESSAGE
from src.producers.text_editor import trunc_str
from src.static.sources import telegram_chat_id


def telegram_prepare_post(translated_message, source, link):
    title_post = '<a href="' + link + '">' + source + '</a>\n'
    return title_post + trunc_str(translated_message, TELEGRAM_MAX_LENGTH_MESSAGE)


@async_retry()
async def telegram_send_message(client, post, url_path):
    return await client.send_message(
        entity=int(telegram_chat_id),
        message=post,
        file=url_path.get("url"),
        parse_mode="html",
        link_preview=False
    )


@async_retry()
async def telegram_send_translated_respond(flag, message_sent, translated_text):
    await message_sent.respond(
        flag + ' ' + trunc_str(translated_text, TELEGRAM_MAX_LENGTH_MESSAGE),
        comment_to=message_sent.id
    )
