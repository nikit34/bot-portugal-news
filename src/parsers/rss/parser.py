import asyncio
import logging
import os

import feedparser
import httpx

from src.files_manager import save_file_tmp_from_url
from src.parsers.rss.channels.com.bbc import check_bbc_com, parse_bbc_com
from src.parsers.rss.channels.pt.abola import check_abola_pt, parse_abola_pt
from src.processor.history_comparator import is_duplicate_message
from src.processor.service import serve, translate_message
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT, REPEAT_REQUESTS
from src.producers.telegram.telegram_api import send_message_api
from src.parsers.rss.user_agents_manager import random_user_agent_headers


logger = logging.getLogger(__name__)


async def rss_wrapper(client, graph, translator, telegram_bot_token, source, rss_link, posted_q):
    try:
        await _rss_parser(client, graph, translator, telegram_bot_token, source, rss_link, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: ' + source + ' rss parser is down\n' + str(e)
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
            message = '&#9888; ERROR: ' + rss_link + ' request is down\n' + str(e)
            logger.error(message)
            await send_message_api(message, telegram_bot_token)
    finally:
        await httpx_client.aclose()

    return response


async def _rss_parser(
        client,
        graph,
        translator,
        telegram_bot_token,
        source,
        rss_link,
        posted_q
):
    response = await _make_request(rss_link, telegram_bot_token)
    feed = feedparser.parse(response.text)

    limit = max(MAX_NUMBER_TAKEN_MESSAGES, len(feed.entries))
    for entry in feed.entries[:limit][::-1]:
        message_text = ''
        link = ''
        image = ''
        if 'abola.pt' in source:
            if check_abola_pt(entry):
                continue
            message_text, link, image = parse_abola_pt(entry)
        elif 'bbc.com' in source:
            if check_bbc_com(entry):
                continue
            message_text, link, image = parse_bbc_com(entry)

        translated_message = translate_message(translator, message_text, 'pt')
        if is_duplicate_message(translated_message, posted_q):
            return

        url_path = await save_file_tmp_from_url(image)

        await serve(client, graph, translator, translated_message, source, link, url_path)

        file_path = url_path.get('path')
        if file_path is not None:
            os.remove(file_path)
