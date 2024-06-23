import logging
import os

from src.files_manager import save_file_tmp_from_telegram
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES
from src.static.sources import telegram_channels
from src.producers.telegram.telegram_api import send_message_api


logger = logging.getLogger(__name__)


async def telegram_wrapper(getter_client, graph, translator, telegram_bot_token, telegram_chat_id, telegram_debug_chat_id, channel, posted_q):
    try:
        await _telegram_parser(getter_client, graph, translator, telegram_chat_id, channel, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: ' + channel + ' telegram parser is down\n' + str(e)
        logger.error(message)
        await send_message_api(message, telegram_bot_token, telegram_debug_chat_id)


async def _telegram_parser(getter_client, graph, translator, telegram_chat_id, channel, posted_q):
    async for message in getter_client.iter_messages(channel, limit=MAX_NUMBER_TAKEN_MESSAGES):

        message_text = message.raw_text
        file = message.file

        if not message_text or file is None:
            continue

        source = telegram_channels.get(message.peer_id.channel_id)
        link = source + '/' + str(message.id)
        channel = '@' + source.split('/')[-1]

        file_path = await save_file_tmp_from_telegram(getter_client, message)

        await serve(getter_client, graph, translator, telegram_chat_id, posted_q, channel, message_text, link, file_path)

        if file_path is not None:
            os.remove(file_path)
