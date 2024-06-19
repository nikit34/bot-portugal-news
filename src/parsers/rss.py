import asyncio
import os

import feedparser
import httpx

from src.files_manager import save_image_tmp_from_url
from src.parsers.channels.com.bbc import check_bbc_com, parse_bbc_com
from src.parsers.channels.pt.abola import check_abola_pt, parse_abola_pt
from src.parsers.channels.ru.sport import check_sport_ru, parse_sport_ru
from src.producers.processor import send_message
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT, REPEAT_REQUESTS
from src.producers.telegram.telegram_api import send_message_api
from src.user_agents_manager import random_user_agent_headers


async def rss_wrapper(client, graph, translator, telegram_bot_token, telegram_chat_id, telegram_debug_chat_id, source, rss_link, posted_q, map_images):
    try:
        await _rss_parser(client, graph, translator, telegram_bot_token, telegram_chat_id, telegram_debug_chat_id, source, rss_link, posted_q, map_images)
    except Exception as e:
        message = '&#9888; ERROR: ' + source + ' parser is down\n' + str(e)
        await send_message_api(message, telegram_bot_token, telegram_debug_chat_id)


async def _make_request(rss_link, telegram_bot_token, telegram_debug_chat_id, repeat=REPEAT_REQUESTS):
    response = None
    httpx_client = httpx.AsyncClient()

    try:
        response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
        response.raise_for_status()
    except Exception as e:
        if repeat > 0:
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            return await _make_request(rss_link, telegram_bot_token, telegram_debug_chat_id, repeat)
        else:
            message = '&#9888; ERROR: ' + rss_link + ' request is down\n' + str(e)
            await send_message_api(message, telegram_bot_token, telegram_debug_chat_id)
    finally:
        await httpx_client.aclose()

    return response


async def _rss_parser(
        client,
        graph,
        translator,
        telegram_bot_token,
        telegram_chat_id,
        telegram_debug_chat_id,
        source,
        rss_link,
        posted_q,
        map_images
):
    response = await _make_request(rss_link, telegram_bot_token, telegram_debug_chat_id)
    feed = feedparser.parse(response.text)

    limit = max(MAX_NUMBER_TAKEN_MESSAGES, len(feed.entries))
    for entry in feed.entries[:limit][::-1]:
        message_text = ''
        link = ''
        image = ''
        if source == 'sport.ru':
            if check_sport_ru(entry):
                continue
            message_text, link, image = parse_sport_ru(entry)
        elif 'abola.pt' in source:
            if check_abola_pt(entry):
                continue
            message_text, link, image = parse_abola_pt(entry)
        elif 'bbc.com' in source:
            if check_bbc_com(entry):
                continue
            message_text, link, image = parse_bbc_com(entry)

        image_path = await save_image_tmp_from_url(image)
        map_images.appendleft(image_path)

        await send_message(client, graph, translator, telegram_chat_id, posted_q, source, message_text, link, image_path)

        map_images.remove(image_path)
        os.remove(image_path)
