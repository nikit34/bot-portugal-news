import asyncio
import logging
import signal
from typing import List, Any

from src.files_manager import SaveFileTelegram
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES
from src.static.sources import telegram_channels
from src.producers.telegram.telegram_api import send_message_api
from src.utils.ci import get_ci_run_url

app_logger = logging.getLogger('app')
stats_logger = logging.getLogger('stats')

CHUNK_SIZE = 10 

async def telegram_wrapper(getter_client, graph, nlp, translator, telegram_bot_token, channel, posted_q):
    app_logger.info(f"[Telegram] Starting Telegram parser for channel: {channel}")
    try:
        await _telegram_parser(getter_client, graph, nlp, translator, channel, posted_q)
        app_logger.info(f"[Telegram] Telegram parser completed successfully for channel: {channel}")
    except Exception as e:
        app_logger.error(f"[Telegram] Error in Telegram parser for channel {channel}", exc_info=True)
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        run_url = get_ci_run_url()
        message = (
            f'ERROR: {channel} telegram parser is down\n{str(e)}{response_content}'
            f'\n<a href="{run_url}">Open CI logs</a>' if run_url else ''
        )
        app_logger.error(message)
        await send_message_api(message, telegram_bot_token)


async def _process_message_chunk(
    messages: List[Any],
    getter_client,
    graph,
    nlp,
    translator,
    channel,
    posted_q
) -> int:
    skipped_count = 0
    for message in messages:
        message_text = message.raw_text

        if not message_text or message.media is None:
            skipped_count += 1
            app_logger.debug(f"[Telegram] Skipping message: {'No text' if not message_text else 'No media'}")
            continue

        source = telegram_channels.get(message.peer_id.channel_id)
        if not source:
            skipped_count += 1
            app_logger.error(f"[Telegram] Channel ID {message.peer_id.channel_id} not found in telegram_channels")
            continue

        try:
            handler = SaveFileTelegram(getter_client, message)
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGUSR1, handler)
            app_logger.debug(f"[Telegram] Created file handler for message: {message_text}")

            await serve(graph, nlp, translator, message_text, handler, posted_q)
            app_logger.debug(f"[Telegram] Successfully processed message: {message_text}")
        except Exception as e:
            app_logger.error(f"[Telegram] Error processing message: {message_text}", exc_info=True)
            skipped_count += 1
    
    return skipped_count


async def _telegram_parser(getter_client, graph, nlp, translator, channel, posted_q):
    app_logger.info(f"[Telegram] Initializing message iteration for channel: {channel}")
    message_count = 0
    skipped_count = 0
    current_chunk = []
    chunks = []
    
    async for message in getter_client.iter_messages(channel, limit=MAX_NUMBER_TAKEN_MESSAGES):
        message_count += 1
        current_chunk.append(message)
        
        if len(current_chunk) >= CHUNK_SIZE:
            chunks.append(current_chunk)
            current_chunk = []
    
    # Добавляем последний чанк, если он не пустой
    if current_chunk:
        chunks.append(current_chunk)
    
    # Параллельная обработка всех чанков
    if chunks:
        app_logger.debug(f"[Telegram] Processing {len(chunks)} chunks in parallel")
        chunk_results = await asyncio.gather(*[
            _process_message_chunk(
                chunk, getter_client, graph, nlp, translator, channel, posted_q
            ) for chunk in chunks
        ])
        skipped_count = sum(chunk_results)

    name_channel = '@' + telegram_channels.get(channel).split('/')[-1]
    stats_logger.info(
        f"[Telegram] Telegram parser statistics for channel {channel}, name: {name_channel}: "
        f"Total messages: {message_count}, "
        f"Processed: {message_count - skipped_count}, "
        f"Skipped: {skipped_count}"
    )
