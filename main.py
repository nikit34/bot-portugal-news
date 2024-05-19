from collections import deque

import httpx
from telethon import TelegramClient

from parsers.bcs import bcs_wrapper
from parsers.rss import rss_wrapper
from parsers.telegram import telegram_parser
from properties_reader import get_secret_key
from history_manager import get_messages_history
from static.settings import COUNT_UNIQUE_MESSAGES
from static.sources import rss_channels, bcs_channels


if __name__ == '__main__':

    api_id = get_secret_key('.', 'API_ID')
    api_hash = get_secret_key('.', 'API_HASH')
    password = get_secret_key('.', 'PASSWORD')
    bot_token = get_secret_key('.', 'TOKEN_BOT')
    chat_id = get_secret_key('.', 'CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(password=password, bot_token=bot_token)

    httpx_client = httpx.AsyncClient()

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    with client:
        feature_history = get_messages_history(client, chat_id)
        history = client.loop.run_until_complete(feature_history)
        posted_q.extend(history)

        client = telegram_parser(
            client=client,
            chat_id=chat_id,
            posted_q=posted_q
        )

        for source, bcs_link in bcs_channels.items():
            client.loop.create_task(bcs_wrapper(
                client=client,
                bot_token=bot_token,
                chat_id=chat_id,
                httpx_client=httpx_client,
                source=source,
                bcs_link=bcs_link,
                posted_q=posted_q
            ))

        for source, rss_link in rss_channels.items():
            client.loop.create_task(rss_wrapper(
                client=client,
                bot_token=bot_token,
                chat_id=chat_id,
                httpx_client=httpx_client,
                source=source,
                rss_link=rss_link,
                posted_q=posted_q
            ))

        try:
            client.run_until_disconnected()
        except Exception as e:
            message = '&#9888; ERROR: Parsers is down\n' + str(e)
            feature = client.send_message(entity=int(chat_id), message=message, parse_mode='html', link_preview=False)
            client.loop.run_until_complete(feature)
        finally:
            client.loop.run_until_complete(httpx_client.aclose())
            client.loop.close()
