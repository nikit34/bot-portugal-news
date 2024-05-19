import random
import asyncio
from collections import deque
import httpx
import feedparser
from telethon import TelegramClient

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, TIMEOUT
from static.sources import rss_channels
from user_agents_manager import random_user_agent_headers


async def rss_wrapper(client, chat_id, source, rss_link, posted_q):
    try:
        await rss_parser(client, chat_id, source, rss_link, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: www.rbc.ru parser is down\n' + str(e)
        feature = client.send_message(entity=int(chat_id), message=message, parse_mode='html', link_preview=False)
        client.loop.run_until_complete(feature)


async def rss_parser(
        client,
        chat_id,
        source,
        rss_link,
        posted_q,
        key=KEY_SEARCH_LENGTH_CHARS,
        timeout=TIMEOUT
):
    httpx_client = httpx.AsyncClient()

    while True:
        try:
            response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
            response.raise_for_status()
        except Exception:
            await asyncio.sleep(timeout * 2 - random.uniform(0, 0.5))
            continue

        feed = feedparser.parse(response.text)

        for entry in feed.entries[:20][::-1]:
            if 'summary' not in entry and 'title' not in entry:
                continue

            summary = entry['summary'] if 'summary' in entry else ''
            title = entry['title'] if 'title' in entry else ''
            message = title + '\n' + summary
            head = message[:key].strip()
            if head in posted_q:
                continue
            posted_q.appendleft(head)

            link = entry['link'] if 'link' in entry else ''
            post = '<a href="' + link + '">' + source + '</a>\n' + message
            await client.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)

        await asyncio.sleep(timeout - random.uniform(0, 0.5))


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')
    chat_id = get_secret_key('..', 'CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(password=password, bot_token=bot_token)

    posted_q = deque(maxlen=20)

    source, rss_link = list(rss_channels.items())[0]
    asyncio.run(rss_parser(client, chat_id, source, rss_link, posted_q))
