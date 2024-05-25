import random
import asyncio
from collections import deque
import httpx
import feedparser

from static.settings import TIMEOUT, KEY_SEARCH_LENGTH_CHARS
from utils import random_user_agent_headers


async def rss_parser(httpx_client, source, rss_link, posted_q, check_pattern_func=None,
                     send_message_func=None):
    '''Парсер rss ленты'''

    while True:
        try:
            response = await httpx_client.get(rss_link, headers=random_user_agent_headers())
            response.raise_for_status()
        except Exception as e:
            await asyncio.sleep(TIMEOUT * 2 - random.uniform(0, 0.5))
            continue

        feed = feedparser.parse(response.text)

        for entry in feed.entries[:20][::-1]:
            if 'summary' not in entry and 'title' not in entry:
                continue

            summary = entry['summary'] if 'summary' in entry else ''
            title = entry['title'] if 'title' in entry else ''

            news_text = f'{title}\n{summary}'

            if not (check_pattern_func is None):
                if not check_pattern_func(news_text):
                    continue

            head = news_text[:KEY_SEARCH_LENGTH_CHARS].strip()

            if head in posted_q:
                continue

            link = entry['link'] if 'link' in entry else ''

            post = f'<b>{source}</b>\n{link}\n{news_text}'

            if send_message_func is None:
                print(post, '\n')
            else:
                await send_message_func(post)

            posted_q.appendleft(head)

        await asyncio.sleep(TIMEOUT - random.uniform(0, 0.5))


if __name__ == "__main__":

    source = 'www.rbc.ru'
    
    rss_link = 'https://rssexport.rbc.ru/rbcnews/news/20/full.rss',

    # Очередь из уже опубликованных постов, чтобы их не дублировать
    posted_q = deque(maxlen=20)

    httpx_client = httpx.AsyncClient()

    asyncio.run(rss_parser(httpx_client, source, rss_link, posted_q))