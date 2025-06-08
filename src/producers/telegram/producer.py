from src.producers.repeater import async_retry
from src.static.settings import TELEGRAM_MAX_LENGTH_MESSAGE
from src.producers.text_editor import trunc_str


def telegram_prepare_post(translated_message):
    return trunc_str(translated_message, TELEGRAM_MAX_LENGTH_MESSAGE)


@async_retry()
async def telegram_send_message(client, post, url_path, context):
    return await client.send_message(
        entity=int(context['self_telegram_chat_id']),
        message=post,
        file=url_path.get("url"),
        parse_mode="html",
        link_preview=False
    )
