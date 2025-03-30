import asyncio
import logging
import signal

from src.files_manager import SaveFileTelegram
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES
from src.static.sources import telegram_channels
from src.producers.telegram.telegram_api import send_message_api
from src.utils.ci import get_ci_run_url

logger = logging.getLogger(__name__)


async def telegram_wrapper(
        getter_client,
        graph,
        nlp,
        translator,
        telegram_bot_token,
        channel,
        storage
):
    logger.info(f"Starting Telegram parser for channel: {channel}")
    try:
        await _telegram_parser(getter_client, graph, nlp, translator, channel, storage)
        logger.info(f"Telegram parser completed successfully for channel: {channel}")
    except Exception as e:
        logger.error(f"Error in Telegram parser for channel {channel}", exc_info=True)
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        run_url = get_ci_run_url()
        message = (
            f'ERROR: {channel} telegram parser is down\n{str(e)}{response_content}'
            f'\n<a href="{run_url}">Open CI logs</a>' if run_url else ''
        )
        logger.error(message)
        await send_message_api(message, telegram_bot_token)


async def _telegram_parser(
        getter_client,
        graph,
        nlp,
        translator,
        channel,
        storage
):
    logger.debug(f"Initializing message iteration for channel: {channel}")
    message_count = 0
    processed_count = 0
    skipped_count = 0

    async for message in getter_client.iter_messages(channel, limit=MAX_NUMBER_TAKEN_MESSAGES):
        message_count += 1
        logger.debug(f"Processing message {message_count}/{MAX_NUMBER_TAKEN_MESSAGES} from channel {channel}")

        message_text = message.raw_text
        message_id = message.id
        logger.debug(f"Message ID: {message_id}, Has text: {bool(message_text)}, Has media: {message.media is not None}")

        if not message_text or message.media is None:
            skipped_count += 1
            logger.debug(f"Skipping message {message_id}: {'No text' if not message_text else 'No media'}")
            continue

        source = telegram_channels.get(message.peer_id.channel_id)
        if not source:
            logger.warning(f"Channel ID {message.peer_id.channel_id} not found in telegram_channels")
            skipped_count += 1
            continue

        channel = '@' + source.split('/')[-1]
        logger.debug(f"Processing message from channel: {channel}")

        try:
            handler = SaveFileTelegram(getter_client, message)
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGUSR1, handler)
            logger.debug(f"Created file handler for message {message_id}")

            await serve(graph, nlp, translator, message_text, handler, storage)
            processed_count += 1
            logger.debug(f"Successfully processed message {message_id}")
        except Exception as e:
            logger.error(f"Error processing message {message_id}", exc_info=True)
            skipped_count += 1

    logger.info(
        f"Telegram parser statistics for channel {channel}: "
        f"Total messages: {message_count}, "
        f"Processed: {processed_count}, "
        f"Skipped: {skipped_count}"
    )
