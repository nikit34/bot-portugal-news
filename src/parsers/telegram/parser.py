import asyncio
import logging
import signal
from typing import List, Any

from telethon.tl.types import MessageMediaWebPage
from src.files_manager import SaveFileTelegram
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, MESSAGE_CHUNK_SIZE
from src.producers.telegram.telegram_api import send_message_api
from src.utils.ci import get_ci_run_url

app_logger = logging.getLogger('app')
stats_logger = logging.getLogger('stats')


async def telegram_wrapper(getter_client, graph, nlp, translator, telegram_bot_token, channel_link, posted_q):
    app_logger.info(f"[Telegram] Starting Telegram parser for channel: {channel_link}")
    try:
        await _telegram_parser(getter_client, graph, nlp, translator, channel_link, posted_q)
        app_logger.info(f"[Telegram] Telegram parser completed successfully for channel: {channel_link}")
    except Exception as e:
        app_logger.error(f"[Telegram] Error in Telegram parser for channel {channel_link}", exc_info=True)
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        run_url = get_ci_run_url()
        message = (
            f'ERROR: {channel_link} telegram parser is down\n{str(e)}{response_content}'
            f'\n<a href="{run_url}">Open CI logs</a>' if run_url else ''
        )
        app_logger.error(message)
        await send_message_api(message, telegram_bot_token)


async def _process_message_chunk(
    message_chunk: List[Any],
    getter_client,
    graph,
    nlp,
    translator,
    posted_q
) -> int:
    skipped_count = 0
    for message in message_chunk:
        message_text = message.raw_text

        if not message_text or not isinstance(message.media, MessageMediaWebPage):
            skipped_count += 1
            app_logger.debug(f"[Telegram] Skipping message: {'No text' if not message_text else 'No media'}")
            continue

        try:
            handler_url_path = SaveFileTelegram(getter_client, message)
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGUSR1, handler_url_path)
            app_logger.debug(f"[Telegram] Created file handler for message: {message_text}")

            await serve(graph, nlp, translator, message_text, handler_url_path, posted_q)
            app_logger.debug(f"[Telegram] Successfully processed message: {message_text}")
        except Exception as e:
            app_logger.error(f"[Telegram] Error processing message: {message_text}", exc_info=True)
            skipped_count += 1
    
    return skipped_count


async def _telegram_parser(getter_client, graph, nlp, translator, channel_link, posted_q):
    app_logger.info(f"[Telegram] Initializing message iteration for channel: {channel_link}")
    message_count = 0
    skipped_count = 0
    current_message_chunk = []
    message_chunks = []
    
    async for message in getter_client.iter_messages(channel_link, limit=MAX_NUMBER_TAKEN_MESSAGES):
        message_count += 1
        current_message_chunk.append(message)
        
        if len(current_message_chunk) >= MESSAGE_CHUNK_SIZE:
            message_chunks.append(current_message_chunk)
            current_message_chunk = []
    
    if current_message_chunk:
        message_chunks.append(current_message_chunk)
    
    if message_chunks:
        app_logger.debug(f"[Telegram] Processing {len(message_chunks)} chunks in parallel")
        chunk_results = await asyncio.gather(*[
            _process_message_chunk(
                message_chunk, getter_client, graph, nlp, translator, posted_q
            ) for message_chunk in message_chunks
        ])
        skipped_count = sum(chunk_results)

    name_channel = '@' + channel_link.split('/')[-1]
    stats_logger.info(
        f"[Telegram] Telegram parser statistics for channel {channel_link}, name: {name_channel}: "
        f"Total messages: {message_count}, "
        f"Processed: {message_count - skipped_count}, "
        f"Skipped: {skipped_count}"
    )
