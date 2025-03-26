import asyncio
import logging
import signal

from src.files_manager import SaveFileTelegram
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES
from src.static.sources import telegram_channels
from src.producers.telegram.telegram_api import send_message_api


logger = logging.getLogger(__name__)


async def telegram_wrapper(getter_client, graph, nlp, translator, telegram_bot_token, channel, posted_q):
    try:
        await _telegram_parser(getter_client, graph, nlp, translator, channel, posted_q)
    except Exception as e:
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        message = 'ERROR: ' + channel + ' telegram parser is down\n' + str(e) + response_content
        logger.error(message)
        await send_message_api(message, telegram_bot_token)


async def _telegram_parser(getter_client, graph, nlp, translator, channel, posted_q):
    async for message in getter_client.iter_messages(channel, limit=MAX_NUMBER_TAKEN_MESSAGES):

        message_text = message.raw_text

        if not message_text or message.media is None:
            continue

        source = telegram_channels.get(message.peer_id.channel_id)
        channel = '@' + source.split('/')[-1]

        handler = SaveFileTelegram(getter_client, message)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGUSR1, handler)

        await serve(graph, nlp, translator, message_text, handler, posted_q)
