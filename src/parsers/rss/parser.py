import asyncio
import logging
import signal

import feedparser
import httpx

from src.files_manager import SaveFileUrl
from src.parsers.rss.channels.com.bbc import check_bbc_com, parse_bbc_com
from src.parsers.rss.channels.pt.abola import check_abola_pt, parse_abola_pt
from src.processor.service import serve
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT, REPEAT_REQUESTS
from src.producers.telegram.telegram_api import send_message_api
from src.parsers.rss.user_agents_manager import random_user_agent_headers


logger = logging.getLogger(__name__)


async def rss_wrapper(graph, nlp, translator, telegram_bot_token, source, rss_link, posted_q):
    try:
        await _rss_parser(graph, nlp, translator, telegram_bot_token, source, rss_link, posted_q)
    except Exception as e:
        message = 'ERROR: ' + source + ' rss parser is down\n' + str(e) + ', response: ' + getattr(e, 'response', {}).get('content', '')
        logger.error(message)
        await send_message_api(message, telegram_bot_token)


async def _make_request(rss_link, telegram_bot_token, repeat=REPEAT_REQUESTS):
    response = None
    httpx_client = httpx.AsyncClient()

    try:
        response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
        response.raise_for_status()
    except Exception as e:
        if repeat > 0:
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            return await _make_request(rss_link, telegram_bot_token, repeat)
        else:
            response_content = getattr(e, 'response', None)
            response_text = response_content.content if response_content else ''
            message = 'ERROR: ' + rss_link + ' request is down\n' + str(e) + ', response: ' + response_text
            logger.error(message)
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
        posted_q
):
    response = await _make_request(rss_link, telegram_bot_token)
    response.raise_for_status()
    feed = feedparser.parse(response.text)

    limit = min(MAX_NUMBER_TAKEN_MESSAGES, len(feed.entries))
    for entry in feed.entries[:limit][::-1]:
        message_text = ''
        image = ''
        if 'abola.pt' in source:
            if check_abola_pt(entry):
                continue
            message_text, image = parse_abola_pt(entry)
        elif 'bbc.com' in source:
            if check_bbc_com(entry):
                continue
            message_text, image = parse_bbc_com(entry)

        handler = SaveFileUrl(image)
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGUSR1, handler)

        await serve(graph, nlp, translator, message_text, handler, posted_q)
