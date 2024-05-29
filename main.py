from collections import deque

import httpx
from telethon import TelegramClient
from googletrans import Translator

from parsers.rss import rss_wrapper
from parsers.telegram import telegram_parser
from parsers.self_telegram import get_messages_history
from properties_reader import get_secret_key
from static.settings import COUNT_UNIQUE_MESSAGES
from static.sources import rss_channels
from telegram_api import send_message_api


if __name__ == '__main__':

    api_id = get_secret_key('.', 'API_ID')
    api_hash = get_secret_key('.', 'API_HASH')
    password = get_secret_key('.', 'PASSWORD')
    bot_token = get_secret_key('.', 'TOKEN_BOT')
    chat_id = get_secret_key('.', 'CHAT_ID')
    debug_chat_id = get_secret_key('.', 'DEBUG_CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(password=password, bot_token=bot_token)

    httpx_client = httpx.AsyncClient()
    translator = Translator(service_urls=['translate.googleapis.com'])

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    with client:
        getter_client = TelegramClient('getter_bot', api_id, api_hash)
        getter_client.start()

        feature_history = get_messages_history(getter_client)
        history = getter_client.loop.run_until_complete(feature_history)
        posted_q.extend(history)

        client.loop.create_task(telegram_parser(
            getter_client=getter_client,
            translator=translator,
            chat_id=chat_id,
            posted_q=posted_q
        ))

        for source, rss_link in rss_channels.items():
            client.loop.create_task(rss_wrapper(
                client=client,
                translator=translator,
                bot_token=bot_token,
                chat_id=chat_id,
                debug_chat_id=debug_chat_id,
                httpx_client=httpx_client,
                source=source,
                rss_link=rss_link,
                posted_q=posted_q
            ))

        try:
            getter_client.run_until_disconnected()
        except Exception as e:
            message = '&#9888; ERROR: Parsers is down\n' + str(e)
            feature = send_message_api(message, bot_token, debug_chat_id)
            client.loop.run_until_complete(feature)
        finally:
            client.loop.run_until_complete(httpx_client.aclose())
            client.loop.close()
