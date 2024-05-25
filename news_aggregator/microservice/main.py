import httpx
import asyncio
from collections import deque
from telethon import TelegramClient

from history_manager import get_messages_history
from parsers.rss import rss_wrapper
from properties_reader import get_secret_key
from telegram_api import send_message_api
from telegram_parser import telegram_parser
from parsers.bcs import bcs_wrapper
from static.settings import COUNT_UNIQUE_MESSAGES
from static.sources import rss_channels, telegram_channels, bcs_channels
from config import api_id, api_hash, chat_id, bot_token


if __name__ == '__main__':

    password = get_secret_key('.', 'PASSWORD')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    bot = TelegramClient('bot', api_id, api_hash, loop=loop)
    bot.start(password=password, bot_token=bot_token)


    async def send_message_callback(post):
        await bot.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)


    client = telegram_parser('gazp', api_id, api_hash, telegram_channels, posted_q, send_message_callback,
                             loop)

    history = loop.run_until_complete(get_messages_history(client, chat_id))

    posted_q.extend(history)

    httpx_client = httpx.AsyncClient()

    for source, rss_link in rss_channels.items():
        loop.create_task(rss_wrapper(
            bot_token=bot_token,
            chat_id=chat_id,
            httpx_client=httpx_client,
            source=source,
            rss_link=rss_link,
            send_message_callback=send_message_callback,
            posted_q=posted_q
        ))

    for source, bcs_link in bcs_channels.items():
        loop.create_task(bcs_wrapper(
            bot_token=bot_token,
            chat_id=chat_id,
            httpx_client=httpx_client,
            source=source,
            bcs_link=bcs_link,
            send_message_callback=send_message_callback,
            posted_q=posted_q
        ))


    try:
        # Запускает все парсеры
        client.run_until_disconnected()

    except Exception as e:
        message = f'&#9888; ERROR: telegram parser (all parsers) is down! \n{e}'
        loop.run_until_complete(send_message_api(message, bot_token,
                                                   chat_id))
    finally:
        loop.run_until_complete(httpx_client.aclose())
        loop.close()
