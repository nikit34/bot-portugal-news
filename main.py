import asyncio
import os
from collections import deque

from telethon import TelegramClient
from googletrans import Translator
import facebook as fb

from src.parsers.rss import rss_wrapper
from src.parsers.telegram import telegram_wrapper
from src.parsers.self_telegram import get_messages_history
from src.properties_reader import get_secret_key
from src.static.settings import COUNT_UNIQUE_MESSAGES
from src.static.sources import rss_channels, telegram_channels, tmp_folder
from src.producers.telegram.telegram_api import send_message_api


async def main():
    telegram_api_id = get_secret_key('.', 'TELEGRAM_API_ID')
    telegram_api_hash = get_secret_key('.', 'TELEGRAM_API_HASH')
    telegram_password = get_secret_key('.', 'TELEGRAM_PASSWORD')
    telegram_bot_token = get_secret_key('.', 'TELEGRAM_TOKEN_BOT')
    telegram_chat_id = get_secret_key('.', 'TELEGRAM_CHAT_ID')
    telegram_debug_chat_id = get_secret_key('.', 'TELEGRAM_DEBUG_CHAT_ID')

    access_token = get_secret_key('.', 'FACEBOOK_ACCESS_TOKEN')

    client = TelegramClient('bot', telegram_api_id, telegram_api_hash)

    graph = fb.GraphAPI(access_token=access_token)

    translator = Translator(service_urls=['translate.googleapis.com'])

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)
    map_images = deque()

    async with client:
        await client.start(password=telegram_password, bot_token=telegram_bot_token)
        getter_client = TelegramClient('getter_bot', telegram_api_id, telegram_api_hash)
        await getter_client.start()

        try:
            history = await get_messages_history(getter_client)
            posted_q.extend(history)

            tasks = []

            for channel in telegram_channels.values():
                task = telegram_wrapper(
                    getter_client=getter_client,
                    graph=graph,
                    translator=translator,
                    telegram_bot_token=telegram_bot_token,
                    telegram_chat_id=telegram_chat_id,
                    telegram_debug_chat_id=telegram_debug_chat_id,
                    channel=channel,
                    posted_q=posted_q,
                    map_images=map_images
                )
                tasks.append(task)

            for source, rss_link in rss_channels.items():
                task = rss_wrapper(
                    client=getter_client,
                    graph=graph,
                    translator=translator,
                    telegram_bot_token=telegram_bot_token,
                    telegram_chat_id=telegram_chat_id,
                    telegram_debug_chat_id=telegram_debug_chat_id,
                    source=source,
                    rss_link=rss_link,
                    posted_q=posted_q,
                    map_images=map_images
                )
                tasks.append(task)

            await asyncio.gather(*tasks)
        except Exception as e:
            message = '&#9888; ERROR: Parsers is down\n' + str(e)
            await send_message_api(message, telegram_bot_token, telegram_debug_chat_id)
        finally:
            for filename in os.listdir(tmp_folder):
                if filename != ".gitkeep":
                    file_path = os.path.join(tmp_folder, filename)
                    os.remove(file_path)


if __name__ == '__main__':
    asyncio.run(main())


def delete_files_except_gitkeep(folder_path):
    if not os.path.exists(folder_path):
        print(f"Папка {folder_path} не существует.")
        return

    # Перебираем все файлы в папке
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        # Проверяем, что это файл и что он не является .gitkeep
        if os.path.isfile(file_path) and filename != ".gitkeep":
            try:
                os.remove(file_path)
                print(f"Файл {file_path} был удалён.")
            except Exception as e:
                print(f"Не удалось удалить файл {file_path}. Ошибка: {e}")
