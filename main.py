import asyncio
from collections import deque

import httpx
from telethon import TelegramClient
from googletrans import Translator

from parsers.rss import rss_wrapper
from parsers.telegram import telegram_wrapper
from parsers.self_telegram import get_messages_history
from properties_reader import get_secret_key
from static.settings import COUNT_UNIQUE_MESSAGES
from static.sources import rss_channels, telegram_channels
from telegram_api import send_message_api


async def main():
    api_id = get_secret_key('.', 'API_ID')
    api_hash = get_secret_key('.', 'API_HASH')
    password = get_secret_key('.', 'PASSWORD')
    bot_token = get_secret_key('.', 'TOKEN_BOT')
    chat_id = get_secret_key('.', 'CHAT_ID')
    debug_chat_id = get_secret_key('.', 'DEBUG_CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)

    httpx_client = httpx.AsyncClient()
    translator = Translator(service_urls=['translate.googleapis.com'])

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    async with client:
        await client.start(password=password, bot_token=bot_token)
        getter_client = TelegramClient('getter_bot', api_id, api_hash)
        await getter_client.start()

        try:
            history = await get_messages_history(getter_client)
            posted_q.extend(history)

            tasks = []

            for channel in telegram_channels.values():
                task = telegram_wrapper(
                    getter_client=getter_client,
                    translator=translator,
                    bot_token=bot_token,
                    chat_id=chat_id,
                    debug_chat_id=debug_chat_id,
                    httpx_client=httpx_client,
                    channel=channel,
                    posted_q=posted_q
                )
                tasks.append(task)

            for source, rss_link in rss_channels.items():
                task = rss_wrapper(
                    client=getter_client,
                    translator=translator,
                    bot_token=bot_token,
                    chat_id=chat_id,
                    debug_chat_id=debug_chat_id,
                    httpx_client=httpx_client,
                    source=source,
                    rss_link=rss_link,
                    posted_q=posted_q
                )
                tasks.append(task)

            await asyncio.gather(*tasks)
        except Exception as e:
            message = '&#9888; ERROR: Parsers is down\n' + str(e)
            await send_message_api(httpx_client, message, bot_token, debug_chat_id)
        finally:
            await httpx_client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
