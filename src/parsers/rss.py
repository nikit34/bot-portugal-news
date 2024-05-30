import asyncio

import feedparser

from src.parsers.channels.com.bbc import check_bbc_com, parse_bbc_com
from src.parsers.channels.pt.abola import check_abola_pt, parse_abola_pt
from src.parsers.channels.ru.sport import check_sport_ru, parse_sport_ru
from src.sender import process_and_send_message
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT
from src.telegram_api import send_message_api
from src.user_agents_manager import random_user_agent_headers


async def rss_wrapper(client, translator, bot_token, chat_id, debug_chat_id, httpx_client, source, rss_link, posted_q):
    try:
        await _rss_parser(client, translator, bot_token, chat_id, debug_chat_id, httpx_client, source, rss_link, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: ' + source + ' parser is down\n' + str(e)
        await send_message_api(httpx_client, message, bot_token, debug_chat_id)


async def _make_request(httpx_client, rss_link, bot_token, debug_chat_id):
    response = None
    repeat = 20
    while repeat > 0:
        try:
            response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
            response.raise_for_status()
            break
        except Exception as e:
            message = '&#9888; ERROR: ' + rss_link + ' request is down\n' + str(e)
            await send_message_api(httpx_client, message, bot_token, debug_chat_id)
            await asyncio.sleep(TIMEOUT)
            repeat -= 1
            continue
    return response


async def _rss_parser(
        client,
        translator,
        bot_token,
        chat_id,
        debug_chat_id,
        httpx_client,
        source,
        rss_link,
        posted_q
):
    response = await _make_request(httpx_client, rss_link, bot_token, debug_chat_id)
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
        await process_and_send_message(client, translator, chat_id, posted_q, source, message_text, link, image)