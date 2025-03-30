import asyncio
import logging
import signal

import feedparser
import httpx

from src.files_manager import SaveFileUrl
from src.parsers.rss.channels.com.bbc import is_valid_bbc_com_entry, parse_bbc_com
from src.parsers.rss.channels.pt.abola import is_valid_abola_entry, parse_abola_pt
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT, REPEAT_REQUESTS
from src.producers.telegram.telegram_api import send_message_api
from src.parsers.rss.user_agents_manager import random_user_agent_headers


logger = logging.getLogger(__name__)


async def rss_wrapper(graph, nlp, translator, telegram_bot_token, source, rss_link, posted_q, run_url=''):
    try:
        logger.info(f"Starting RSS parser for source: {source}")
        logger.debug(f"RSS link: {rss_link}")
        await _rss_parser(graph, nlp, translator, telegram_bot_token, source, rss_link, posted_q, run_url)
    except Exception as e:
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        message = (
            f'ERROR: {source} rss parser is down\n{str(e)}{response_content}'
            f'\n<a href="{run_url}">Открыть логи CI</a>' if run_url else ''
        )
        logger.error(message, exc_info=True)
        await send_message_api(message, telegram_bot_token)


async def _make_request(rss_link, telegram_bot_token, repeat=REPEAT_REQUESTS, run_url=''):
    response = None
    httpx_client = httpx.AsyncClient()
    logger.debug(f"Making request to {rss_link} (attempts left: {repeat})")

    try:
        response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
        response.raise_for_status()
        logger.debug(f"Request successful, status code: {response.status_code}")
    except Exception as e:
        if repeat > 0:
            logger.warning(f"Request failed, retrying in {TIMEOUT} seconds. Error: {str(e)}")
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            return await _make_request(rss_link, telegram_bot_token, repeat, run_url)
        else:
            response_content = getattr(e, 'response', None)
            response_text = ', response: ' + response_content.content if response_content else ''
            message = (
                f'ERROR: {rss_link} request is down\n{str(e)}{response_text}'
                f'\n<a href="{run_url}">Открыть логи CI</a>' if run_url else ''
            )
            logger.error(message, exc_info=True)
            await send_message_api(message, telegram_bot_token)
    finally:
        await httpx_client.aclose()

    return response


async def _rss_parser(
        graph,
        nlp,
        translator,
        telegram_bot_token,
        source,
        rss_link,
        posted_q,
        run_url=''
):
    logger.info(f"Starting RSS parser for {source}")
    response = await _make_request(rss_link, telegram_bot_token, REPEAT_REQUESTS, run_url)
    response.raise_for_status()
    feed = feedparser.parse(response.text)
    logger.debug(f"Feed parsed successfully, found {len(feed.entries)} entries")

    limit = min(MAX_NUMBER_TAKEN_MESSAGES, len(feed.entries))
    logger.info(f"Processing {limit} entries from {source}")
    
    for entry in feed.entries[:limit][::-1]:
        message_text = ''
        image = ''
        logger.debug(f"Processing entry: {entry.get('title', 'No title')}")
        
        if 'abola.pt' in source:
            if not is_valid_abola_entry(entry):
                logger.debug("Entry skipped - invalid Abola entry")
                continue
            message_text, image = parse_abola_pt(entry)
        elif 'bbc.com' in source:
            if not is_valid_bbc_com_entry(entry):
                logger.debug("Entry skipped - invalid BBC entry")
                continue
            message_text, image = parse_bbc_com(entry)

        handler = SaveFileUrl(image)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGUSR1, handler)

        await serve(graph, nlp, translator, message_text, handler, posted_q)
