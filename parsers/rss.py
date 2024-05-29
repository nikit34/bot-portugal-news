import random
import asyncio
from collections import deque
import feedparser
import httpx
from googletrans import Translator
from telethon import TelegramClient

from history_comparator import compare_messages
from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, TIMEOUT, MAX_LENGTH_MESSAGE
from static.sources import rss_channels
from telegram_api import send_message_api
from text_editor import trunc_str
from user_agents_manager import random_user_agent_headers


async def rss_wrapper(client, translator, bot_token, chat_id, debug_chat_id, httpx_client, source, rss_link, posted_q):
    try:
        await rss_parser(client, translator, chat_id, httpx_client, source, rss_link, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: ' + source + ' parser is down\n' + str(e)
        await send_message_api(message, bot_token, debug_chat_id)


async def rss_parser(
        client,
        translator,
        chat_id,
        httpx_client,
        source,
        rss_link,
        posted_q
):
    while True:
        try:
            response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
            response.raise_for_status()
        except Exception:
            await asyncio.sleep(TIMEOUT * 2 - random.uniform(0, 0.5))
            continue

        feed = feedparser.parse(response.text)

        for entry in feed.entries[:20][::-1]:
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

        await asyncio.sleep(TIMEOUT - random.uniform(0, 0.5))


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')
    chat_id = get_secret_key('..', 'CHAT_ID')
    debug_chat_id = get_secret_key('..', 'DEBUG_CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(password=password, bot_token=bot_token)

    translator = Translator(service_urls=['translate.googleapis.com'])

    httpx_client = httpx.AsyncClient()

    posted_q = deque(maxlen=20)

    for source, rss_link in rss_channels.items():
        asyncio.run(rss_wrapper(client, translator, bot_token, chat_id, debug_chat_id, httpx_client, source, rss_link, posted_q))
