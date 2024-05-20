import random
import asyncio
from collections import deque
import httpx
from scrapy.selector import Selector
from telethon import TelegramClient

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, TIMEOUT
from static.sources import bcs_channels
from telegram_api import send_message_api
from user_agents_manager import random_user_agent_headers


async def bcs_wrapper(bot_token, chat_id, httpx_client, source, bcs_link, send_message_callback, posted_q):
    try:
        await bcs_parser(httpx_client, source, bcs_link, send_message_callback, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: ' + source + ' parser is down\n' + str(e)
        await send_message_api(message, bot_token, chat_id)


async def bcs_parser(
        httpx_client,
        source,
        bcs_link,
        send_message_callback,
        posted_q,
        key=KEY_SEARCH_LENGTH_CHARS,
        timeout=TIMEOUT
):
    while True:
        try:
            response = await httpx_client.get(bcs_link, headers=random_user_agent_headers())
            response.raise_for_status()
        except Exception:
            await asyncio.sleep(timeout * 2 + random.uniform(0, 0.5))
            continue

        selector = Selector(text=response.text)

        for row in selector.xpath('//div[@class="feed__list"]/div/div')[::-1]:

            raw_text = row.xpath('*//text()').extract()

            title = raw_text[3] if len(raw_text) > 3 else ''
            summary = raw_text[5] if len(raw_text) > 5 else ''
            if 'ксперт' in summary:
                title = title + ', ' + summary
                summary = raw_text[11] if len(raw_text) > 11 else ''

            message = title + '\n' + summary
            head = message[:key].strip()
            if head in posted_q:
                continue
            posted_q.appendleft(head)

            raw_link = row.xpath('a/@href').extract()
            link = raw_link[0] if len(raw_link) > 0 else ''
            if 'author' in link:
                link = raw_link[1] if len(raw_link) > 1 else ''

            post = '<a href="' + source + link + '">' + source + '</a>\n' + message
            await send_message_callback(post)

        await asyncio.sleep(timeout + random.uniform(0, 0.5))


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')
    chat_id = get_secret_key('..', 'CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(password=password, bot_token=bot_token)

    httpx_client = httpx.AsyncClient()

    posted_q = deque(maxlen=20)

    async def send_message_callback(post):
        await client.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)

    for source, bcs_link in bcs_channels.items():
        asyncio.run(bcs_parser(httpx_client, source, bcs_link, send_message_callback, posted_q))
