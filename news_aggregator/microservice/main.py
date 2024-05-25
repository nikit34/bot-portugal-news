import httpx
import asyncio
import logging
from collections import deque
from telethon import TelegramClient

from telegram_parser import telegram_parser
from parsers.bcs import bcs_wrapper
from static.settings import COUNT_UNIQUE_MESSAGES
from static.sources import rss_channels, telegram_channels, bcs_channels
from rss_parser import rss_parser
from utils import create_logger, get_history, send_error_message
from config import api_id, api_hash, chat_id, bot_token


###########################
# Можно добавить телеграм канал, rss ссылку или изменить фильтр новостей


def check_pattern_func(text):
    '''Вибирай только посты или статьи про газпром или газ'''
    # words = text.lower().split()
    #
    # key_words = [
    #     'газп',     # газпром
    #     'газо',     # газопровод, газофикация...
    #     'поток',    # сервеный поток, северный поток 2, южный поток
    #     'спг',      # спг - сжиженный природный газ
    #     'gazp',
    # ]
    #
    # for word in words:
    #     if 'газ' in word and len(word) < 6:  # газ, газу, газом, газа
    #         return True
    #
    #     for key in key_words:
    #         if key in word:
    #             return True
    #
    # return False
    return True




posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)


###########################


logger = create_logger('gazp')
logger.info('Start...')

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

tele_logger = create_logger('telethon', level=logging.ERROR)

bot = TelegramClient('bot', api_id, api_hash,
                     base_logger=tele_logger, loop=loop)
bot.start(bot_token=bot_token)


async def send_message_callback(post):
    await client.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)


async def send_message_func(text):
    '''Отправляет посты в канал через бот'''
    await bot.send_message(entity=chat_id,
                           parse_mode='html', link_preview=False, message=text)

    logger.info(text)


# Телеграм парсер
client = telegram_parser('gazp', api_id, api_hash, telegram_channels, posted_q, check_pattern_func, send_message_func,
                         tele_logger, loop)


# Список из уже опубликованных постов, чтобы их не дублировать
history = loop.run_until_complete(get_history(client, chat_id))

posted_q.extend(history)

httpx_client = httpx.AsyncClient()

# Добавляй в текущий event_loop rss парсеры
for source, rss_link in rss_channels.items():

    # https://docs.python-guide.org/writing/gotchas/#late-binding-closures
    async def wrapper(source, rss_link):
        try:
            await rss_parser(httpx_client, source, rss_link, posted_q,
                             check_pattern_func,
                             send_message_func, logger)
        except Exception as e:
            message = f'&#9888; ERROR: {source} parser is down! \n{e}'
            await send_error_message(message, bot_token, chat_id, logger)

    loop.create_task(wrapper(source, rss_link))


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
    loop.run_until_complete(send_error_message(message, bot_token,
                                               chat_id, logger))
finally:
    loop.run_until_complete(httpx_client.aclose())
    loop.close()
