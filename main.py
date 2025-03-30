import asyncio
import logging
from collections import deque
import os

import spacy
from telethon import TelegramClient
from googletrans import Translator
import facebook as fb

from src.files_manager import clean_tmp_folder
from src.parsers.facebook.parser import get_published_messages
from src.parsers.rss.parser import rss_wrapper
from src.parsers.telegram.parser import telegram_wrapper
from src.properties_reader import get_secret_key
from src.static.settings import COUNT_UNIQUE_MESSAGES
from src.static.sources import rss_channels, telegram_channels
from src.producers.telegram.telegram_api import send_message_api
from src.utils.logger import setup_logging
from src.utils.ci import get_ci_run_url
from src.storage.post_history_storage import PostHistoryStorage

setup_logging()
logger = logging.getLogger(__name__)

logger.info("Starting bot application")

async def main():
    logger.info("Initializing main application")
    
    logger.debug("Loading secret keys")
    telegram_api_id = get_secret_key('.', 'TELEGRAM_API_ID')
    telegram_api_hash = get_secret_key('.', 'TELEGRAM_API_HASH')
    telegram_password = get_secret_key('.', 'TELEGRAM_PASSWORD')
    telegram_bot_token = get_secret_key('.', 'TELEGRAM_TOKEN_BOT')
    facebook_access_token = get_secret_key('.', 'FACEBOOK_ACCESS_TOKEN')
    logger.debug("Secret keys loaded successfully")

    logger.info("Initializing Telegram clients")
    client = TelegramClient('bot', telegram_api_id, telegram_api_hash)
    getter_client = TelegramClient('getter_bot', telegram_api_id, telegram_api_hash)
    logger.debug("Telegram clients created")

    logger.info("Initializing Facebook Graph API")
    graph = fb.GraphAPI(access_token=facebook_access_token)
    logger.debug("Facebook Graph API initialized")

    logger.info("Loading NLP model and translator")
    nlp = spacy.load('pt_core_news_sm')
    translator = Translator(service_urls=['translate.googleapis.com'])
    logger.debug("NLP model and translator loaded successfully")

    logger.info("Initializing Redis storage")
    storage = PostHistoryStorage()
    logger.debug("Redis storage initialized")

    logger.info("Starting Telegram clients")
    tasks = [
        client.start(password=telegram_password, bot_token=telegram_bot_token),
        getter_client.start()
    ]
    await asyncio.gather(*tasks)
    logger.info("Telegram clients started successfully")

    try:
        logger.info("Fetching message history from Facebook")
        history = get_published_messages(graph, COUNT_UNIQUE_MESSAGES)
        logger.info(f"Loaded {len(history)} messages from Facebook history")

        logger.info("Preparing parsing tasks")
        tasks = []

        logger.info(f"Adding tasks for {len(telegram_channels)} Telegram channels")
        for channel_name, channel in telegram_channels.items():
            logger.debug(f"Adding task for Telegram channel: {channel_name}")
            task = telegram_wrapper(
                getter_client=getter_client,
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                channel=channel,
                storage=storage
            )
            tasks.append(task)

        logger.info(f"Adding tasks for {len(rss_channels)} RSS channels")
        for source, rss_link in rss_channels.items():
            logger.debug(f"Adding task for RSS source: {source}")
            task = rss_wrapper(
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                source=source,
                rss_link=rss_link,
                storage=storage
            )
            tasks.append(task)

        logger.info(f"Starting {len(tasks)} parsing tasks")
        await asyncio.gather(*tasks)
        logger.info("All parsing tasks completed successfully")
    except Exception as e:
        logger.error("Critical error occurred during execution", exc_info=True)
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        run_url = get_ci_run_url()
        message = (
            f'ERROR: Parsers is down\n{str(e)}{response_content}'
            f'\n<a href="{run_url}">Open CI logs</a>' if run_url else ''
        )
        logger.error(message)
        await send_message_api(message, telegram_bot_token)
    finally:
        logger.info("Cleaning up temporary files")
        clean_tmp_folder()
        logger.info("Cleanup completed")


if __name__ == '__main__':
    try:
        logger.info("Starting application")
        asyncio.run(main())
        logger.info("Application completed successfully")
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.critical("Application crashed", exc_info=True)
