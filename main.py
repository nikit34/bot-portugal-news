import asyncio
from collections import deque

import httpx
from telethon import TelegramClient

from parsers.bcs import bcs_wrapper
from parsers.rss import rss_wrapper
from parsers.telegram import telegram_parser, get_messages_history
from properties_reader import get_secret_key
from static.settings import COUNT_UNIQUE_MESSAGES
from static.sources import rss_channels, bcs_channels
from telegram_api import send_message_api


if __name__ == '__main__':

    api_id = get_secret_key('.', 'API_ID')
    api_hash = get_secret_key('.', 'API_HASH')
    password = get_secret_key('.', 'PASSWORD')
    bot_token = get_secret_key('.', 'TOKEN_BOT')
    chat_id = get_secret_key('.', 'CHAT_ID')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = TelegramClient('bot', api_id, api_hash, loop=loop)
    client.start(password=password, bot_token=bot_token)

    httpx_client = httpx.AsyncClient()

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    with client:

        async def send_message_callback(post):
            await client.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)


        getter_client = telegram_parser(
            session='getter_bot',
            api_id=api_id,
            api_hash=api_hash,
            loop=loop,
            chat_id=chat_id,
            posted_q=posted_q
        )

        feature_history = get_messages_history(getter_client, chat_id)
        history = loop.run_until_complete(feature_history)
        posted_q.extend(history)

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

        try:
            getter_client.run_until_disconnected()
        except Exception as e:
            message = '&#9888; ERROR: Parsers is down\n' + str(e)
            feature = send_message_api(text=message, bot_token=bot_token, chat_id=chat_id)
            loop.run_until_complete(feature)
        finally:
            loop.run_until_complete(httpx_client.aclose())
            loop.close()
