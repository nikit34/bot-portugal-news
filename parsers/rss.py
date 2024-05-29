import asyncio

import feedparser

from history_comparator import compare_messages
from static.settings import KEY_SEARCH_LENGTH_CHARS, MAX_LENGTH_MESSAGE, MAX_NUMBER_TAKEN_MESSAGES, TIMEOUT
from telegram_api import send_message_api
from text_editor import trunc_str
from user_agents_manager import random_user_agent_headers


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
        required_keys = ('summary', 'title', 'rbc_news_url', 'link')
        if not all(entry.get(key) for key in required_keys):
            continue

        summary = entry.get('summary')
        title = entry.get('title')
        message = title + '\n' + summary

        link = entry.get('link')
        image = entry.get('rbc_news_url')

        translated = translator.translate(message, dest='pt', src='ru')
        translated_message = translated.text

        head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()
        if compare_messages(head, posted_q):
            continue
        posted_q.appendleft(head)

        title_post = '<a href="' + link + '">' + source + '</a>\n'
        post = title_post + trunc_str(translated_message, MAX_LENGTH_MESSAGE)

        await client.send_message(
            entity=int(chat_id),
            message=post,
            file=image,
            parse_mode='html',
            link_preview=False
        )
