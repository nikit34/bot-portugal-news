import random
import asyncio
from collections import deque
import httpx
from scrapy.selector import Selector
from telethon import TelegramClient

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, TIMEOUT
from static.sources import bcs_channels
from user_agents_manager import random_user_agent_headers


async def bcs_wrapper(client, chat_id, source, bcs_link, posted_q):
    try:
        await bcs_parser(client, chat_id, source, bcs_link, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: bcs-express.ru parser is down\n' + str(e)
        await client.send_message(entity=int(chat_id), message=message, parse_mode='html', link_preview=False)


async def bcs_parser(
        client,
        chat_id,
        source,
        bcs_link,
        posted_q,
        key=KEY_SEARCH_LENGTH_CHARS,
        timeout=TIMEOUT
):
    httpx_client = httpx.AsyncClient()

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
                title = f'{title}, {summary}'
                summary = raw_text[11] if len(raw_text) > 11 else ''

            message = f'{title}\n{summary}'
            head = message[:key].strip()
            if head in posted_q:
                continue
            posted_q.appendleft(head)

            raw_link = row.xpath('a/@href').extract()
            link = raw_link[0] if len(raw_link) > 0 else ''
            if 'author' in link:
                link = raw_link[1] if len(raw_link) > 1 else ''

            post = '<a href="' + source + link + '">' + source + '</a>\n' + message
            await client.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)

        await asyncio.sleep(timeout + random.uniform(0, 0.5))


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')
    chat_id = get_secret_key('..', 'CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(password=password, bot_token=bot_token)

    posted_q = deque(maxlen=20)

    for source, bcs_link in bcs_channels.items():
        asyncio.run(bcs_parser(client, chat_id, source, bcs_link, posted_q))
