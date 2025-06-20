import asyncio
import logging
import argparse
from collections import deque

import spacy
from telethon import TelegramClient
from googletrans import Translator
import facebook as fb

from src.files_manager import clean_tmp_folder
from src.parsers.facebook.self_parser import get_facebook_published_messages
from src.parsers.telegram.self_parser import get_telegram_published_messages
from src.processor.history_comparator import process_post_histories
from src.parsers.rss.parser import rss_wrapper
from src.parsers.telegram.parser import telegram_wrapper
from src.properties_reader import get_secret_key
from src.static.settings import COUNT_UNIQUE_MESSAGES
from src.static.sources import get_config, Platform
from src.producers.telegram.telegram_api import send_message_api
from src.utils.logger import setup_logging
from src.utils.ci import get_ci_run_url

setup_logging()
app_logger = logging.getLogger('app')

app_logger.info("Starting bot application")

async def main(config_name):
    app_logger.info(f"Initializing main application with config: {config_name}")
    
    context = get_config(config_name)
    
    app_logger.debug("Loading secret keys")
    telegram_api_id = get_secret_key('.', 'TELEGRAM_API_ID')
    telegram_api_hash = get_secret_key('.', 'TELEGRAM_API_HASH')
    telegram_bot_token = get_secret_key('.', 'TELEGRAM_TOKEN_BOT')
    facebook_access_token = get_secret_key('.', 'FACEBOOK_ACCESS_TOKEN')
    app_logger.debug("Secret keys loaded successfully")

    app_logger.info("Initializing Telegram clients")
    client = TelegramClient('bot', telegram_api_id, telegram_api_hash)
    getter_client = TelegramClient('getter_bot', telegram_api_id, telegram_api_hash)
    app_logger.debug("Telegram clients created")

    app_logger.info("Initializing Facebook Graph API")
    graph = fb.GraphAPI(access_token=facebook_access_token)
    app_logger.debug("Facebook Graph API initialized")

    app_logger.info("Loading NLP model and translator")
    nlp = spacy.load('pt_core_news_sm')
    translator = Translator(service_urls=['translate.googleapis.com'])
    app_logger.debug("NLP model and translator loaded successfully")

    app_logger.info(f"Initializing message queue with max length: {COUNT_UNIQUE_MESSAGES}")
    posted_d = {
        Platform.ALL: deque(maxlen=COUNT_UNIQUE_MESSAGES),
        Platform.TELEGRAM: deque(maxlen=COUNT_UNIQUE_MESSAGES),
        Platform.FACEBOOK: deque(maxlen=COUNT_UNIQUE_MESSAGES)
    }
    app_logger.debug("Message queue initialized")

    app_logger.info("Starting Telegram clients")
    tasks = [
        client.start(),
        getter_client.start()
    ]
    await asyncio.gather(*tasks)
    app_logger.info("Telegram clients started successfully")

    try:
        app_logger.info("Fetching message history from Facebook and Telegram")
        facebook_history = get_facebook_published_messages(graph, context, COUNT_UNIQUE_MESSAGES)
        app_logger.info(f"Loaded {len(facebook_history)} messages from Facebook history")
        telegram_history = await get_telegram_published_messages(client, COUNT_UNIQUE_MESSAGES, context)
        app_logger.info(f"Loaded {len(telegram_history)} messages from Telegram history")
        
        posted_d = process_post_histories(facebook_history, telegram_history)
        app_logger.info(f"ALL: {len(posted_d[Platform.ALL])}, Facebook: {len(posted_d[Platform.FACEBOOK])}, Telegram: {len(posted_d[Platform.TELEGRAM])}")

        app_logger.info("Preparing parsing tasks")
        tasks = []

        app_logger.info(f"Adding tasks for {len(context['telegram_channels'])} Telegram channels")
        for channel_link in context['telegram_channels']:
            app_logger.debug(f"Adding task for Telegram channel: {channel_link}")
            task = telegram_wrapper(
                client=client,
                getter_client=getter_client,
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                channel_link=channel_link,
                posted_d=posted_d,
                context=context
            )
            tasks.append(task)

        app_logger.info(f"Adding tasks for {len(context['rss_channels'])} RSS channels")
        for source, rss_link in context['rss_channels'].items():
            app_logger.debug(f"Adding task for RSS source: {rss_link}")
            task = rss_wrapper(
                client=client,
                graph=graph,
                nlp=nlp,
                translator=translator,
                telegram_bot_token=telegram_bot_token,
                source=source,
                rss_link=rss_link,
                posted_d=posted_d,
                context=context
            )
            tasks.append(task)

        app_logger.info(f"Starting {len(tasks)} parsing tasks")
        await asyncio.gather(*tasks)
        app_logger.info("All parsing tasks completed successfully")
    except Exception as e:
        app_logger.error("Critical error occurred during execution", exc_info=True)
        response = getattr(e, 'response', None)
        response_content = ', response: ' + response.content if response else ''
        run_url = get_ci_run_url()
        message = (
            f'ERROR: Parsers is down\n{str(e)}{response_content}'
            f'\n<a href="{run_url}">Open CI logs</a>' if run_url else ''
        )
        app_logger.error(message)
        await send_message_api(message, telegram_bot_token, context)
    finally:
        app_logger.info("Cleaning up temporary files")
        clean_tmp_folder()
        app_logger.info("Cleanup completed")


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Bot for collecting and posting news')
        parser.add_argument('--config', type=str, default='football',
                          help='Configuration to use (football or food)')
        args = parser.parse_args()

        app_logger.info("Starting application")
        asyncio.run(main(args.config))
        app_logger.info("Application completed successfully")
    except KeyboardInterrupt:
        app_logger.info("Application interrupted by user")
    except Exception as e:
        app_logger.critical("Application crashed", exc_info=True)
