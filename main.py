import asyncio
import logging
from collections import deque

import spacy
from telethon import TelegramClient
from googletrans import Translator
import facebook as fb

from src.files_manager import clean_tmp_folder
from src.parsers.rss.parser import rss_wrapper
from src.parsers.telegram.parser import telegram_wrapper
from src.parsers.telegram.self_parser import get_messages_history
from src.properties_reader import get_secret_key
from src.static.settings import COUNT_UNIQUE_MESSAGES
from src.static.sources import rss_channels, telegram_channels
from src.producers.telegram.telegram_api import send_message_api


logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def main():
    telegram_api_id = get_secret_key('.', 'TELEGRAM_API_ID')
    telegram_api_hash = get_secret_key('.', 'TELEGRAM_API_HASH')
    telegram_password = get_secret_key('.', 'TELEGRAM_PASSWORD')
    telegram_bot_token = get_secret_key('.', 'TELEGRAM_TOKEN_BOT')

    facebook_access_token = get_secret_key('.', 'FACEBOOK_ACCESS_TOKEN')

    client = TelegramClient('bot', telegram_api_id, telegram_api_hash)
    getter_client = TelegramClient('getter_bot', telegram_api_id, telegram_api_hash)

    graph = fb.GraphAPI(access_token=facebook_access_token)

    nlp = spacy.load('pt_core_news_sm')
    translator = Translator(service_urls=['translate.googleapis.com'])

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    tasks = [
        client.start(password=telegram_password, bot_token=telegram_bot_token),
        getter_client.start()
    ]
    await asyncio.gather(*tasks)

    try:
        history = await get_messages_history(getter_client)
        posted_q.extend(history)

        tasks = []

        for channel in telegram_channels.values():
            task = telegram_wrapper(
                getter_client=getter_client,
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                channel=channel,
                posted_q=posted_q
            )
            tasks.append(task)

        for source, rss_link in rss_channels.items():
            task = rss_wrapper(
                client=getter_client,
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                source=source,
                rss_link=rss_link,
                posted_q=posted_q
            )
            tasks.append(task)

        await asyncio.gather(*tasks)
    except Exception as e:
        message = '&#9888; ERROR: Parsers is down\n' + str(e)
        logger.error(message)
        await send_message_api(message, telegram_bot_token)
    finally:
        clean_tmp_folder()


if __name__ == '__main__':
    asyncio.run(main())
