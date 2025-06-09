import asyncio
import logging
import signal

import feedparser
import httpx

from src.files_manager import SaveFileUrl
from src.parsers.rss.channels.com.bbc import is_valid_bbc_com_entry, parse_bbc_com
from src.parsers.rss.channels.pt.abola import is_valid_abola_entry, parse_abola_pt
from src.parsers.rss.channels.hin.sportstar import is_valid_sportstar_entry, parse_sportstar_entry
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT, REPEAT_REQUESTS, MESSAGE_CHUNK_SIZE
from src.producers.telegram.telegram_api import send_message_api
from src.parsers.rss.user_agents_manager import random_user_agent_headers
from src.utils.ci import get_ci_run_url


app_logger = logging.getLogger('app')
stats_logger = logging.getLogger('stats')


async def rss_wrapper(client, graph, nlp, translator, telegram_bot_token, source, rss_link, posted_d, context):
    try:
        app_logger.info(f"[RSS] Starting RSS parser for source: {source}, RSS link: {rss_link}")
        await _rss_parser(client, graph, nlp, translator, telegram_bot_token, source, rss_link, posted_d, context)
        app_logger.info(f"[RSS] RSS parser completed successfully for source: {source}, RSS link: {rss_link}")
    except Exception as e:
        app_logger.error(f"[RSS] Error in RSS parser for source: {source}, RSS link: {rss_link}", exc_info=True)
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        run_url = get_ci_run_url()
        message = (
            f'ERROR: {source} rss parser is down\n{str(e)}{response_content}'
            f'\n<a href="{run_url}">Open CI logs</a>' if run_url else ''
        )
        app_logger.error(message, exc_info=True)
        await send_message_api(message, telegram_bot_token, context)


async def _make_request(rss_link, telegram_bot_token, context, repeat=REPEAT_REQUESTS):
    response = None
    httpx_client = httpx.AsyncClient()
    app_logger.debug(f"[RSS] Making request to {rss_link} (attempts left: {repeat})")

    try:
        response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
        response.raise_for_status()
        app_logger.debug(f"[RSS] Request successful, status code: {response.status_code}")
    except Exception as e:
        error_message = f"[RSS] Request failed, retrying in {repeat} seconds. Error: {str(e)}"
        if hasattr(e, 'response'):
            error_message += f", Status code: {e.response.status_code}"
        app_logger.warning(error_message)
        
        if repeat > 0:
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            return await _make_request(rss_link, telegram_bot_token, context, repeat)
        else:
            response_content = getattr(e, 'response', None)
            response_text = ', response: ' + response_content.content if response_content else ''
            run_url = get_ci_run_url()
            message = (
                f'ERROR: {rss_link} request is down\n{str(e)}{response_text}'
                f'\n<a href="{run_url}">Open CI logs</a>' if run_url else ''
            )
            app_logger.error(message, exc_info=True)
            await send_message_api(message, telegram_bot_token, context)
    finally:
        await httpx_client.aclose()

    return response


async def _process_entry(
    entry,
    source,
    client,
    graph,
    nlp,
    translator,
    posted_d,
    context
):
    message_text = ''
    image = ''
    
    if 'abola.pt' in source:
        if not is_valid_abola_entry(entry):
            app_logger.debug("Entry skipped - invalid Abola entry")
            return False
        message_text, image = parse_abola_pt(entry)
    elif 'bbc.com' in source:
        if not is_valid_bbc_com_entry(entry):
            app_logger.debug("Entry skipped - invalid BBC entry")
            return False
        message_text, image = parse_bbc_com(entry)
    elif 'sportstar.thehindu.com' in source:
        if not is_valid_sportstar_entry(entry):
            app_logger.debug("Entry skipped - invalid Sportstar entry")
            return False
        message_text, image = parse_sportstar_entry(entry)

    if not message_text or not image:
        app_logger.debug(f"[RSS] Skipping entry: {'No text' if not message_text else 'No image'}")
        return False

    try:
        handler_url_path = SaveFileUrl(image)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGUSR1, handler_url_path)
        app_logger.debug(f"[RSS] Created file handler for entry: {message_text}")

        await serve(client, graph, nlp, translator, message_text, handler_url_path, posted_d, context)
        app_logger.debug(f"[RSS] Successfully processed entry: {message_text}")
        return True
    except Exception as e:
        app_logger.error(f"[RSS] Error processing entry: {message_text}", exc_info=True)
        return False

async def _process_entry_chunk(
    entry_chunk,
    source,
    client,
    graph,
    nlp,
    translator,
    posted_d,
    context
):
    skipped_count = 0
    tasks = []
    
    for entry in entry_chunk:
        task = _process_entry(entry, source, client, graph, nlp, translator, posted_d, context)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    skipped_count = sum(1 for result in results if not result)
    
    return skipped_count

async def _rss_parser(
        client,
        graph,
        nlp,
        translator,
        telegram_bot_token,
        source,
        rss_link,
        posted_d,
        context
):
    app_logger.info(f"[RSS] Starting RSS parser for {source}, RSS link: {rss_link}")
    response = await _make_request(rss_link, telegram_bot_token, context)
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    app_logger.debug(f"[RSS] Feed parsed successfully, found {len(feed.entries)} entries")

    limit = min(MAX_NUMBER_TAKEN_MESSAGES, len(feed.entries))
    app_logger.info(f"[RSS] Processing {limit} entries from {source}")
    
    entries = feed.entries[:limit][::-1]
    entries_chunks = [entries[i:i + MESSAGE_CHUNK_SIZE] for i in range(0, len(entries), MESSAGE_CHUNK_SIZE)]
    
    skipped_count = 0
    
    for entry_chunk in entries_chunks:
        skipped_count += await _process_entry_chunk(entry_chunk, source, client, graph, nlp, translator, posted_d, context)

    stats_logger.info(
        f"[RSS] RSS parser statistics for {source}, RSS link: {rss_link}: "
        f"Total entries: {limit}, "
        f"Processed: {limit - skipped_count}, "
        f"Skipped: {skipped_count}"
    )
