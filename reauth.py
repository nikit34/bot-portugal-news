"""Перевыпуск Telegram-сессии ЧИТАЮЩЕГО аккаунта (getter_bot).

Два режима:

    python reauth.py                 # файловая сессия getter_bot.session (локальная разработка)
    python reauth.py --string        # StringSession для GitHub Secret TELEGRAM_SESSION (CI)

CI авторизуется секретом TELEGRAM_SESSION. Когда Telegram эту сессию отзывает,
telethon в CI молча уходит в интерактивный логин и прогон падает с EOFError
(«Please enter your phone»), т.е. бот перестаёт публиковать ВООБЩЕ. Лечится
только здесь: логин интерактивный (телефон -> код из Telegram -> пароль 2FA),
из CI его не сделать.

    export TELEGRAM_API_ID=... TELEGRAM_API_HASH=...
    python reauth.py --string
    # вывод вставить в GitHub: Settings -> Secrets -> TELEGRAM_SESSION
    # или: gh secret set TELEGRAM_SESSION
"""
import asyncio
import os
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession

args = [a for a in sys.argv[1:] if a != '--string']
as_string = '--string' in sys.argv
session_name = args[0] if args else 'getter_bot'
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']


async def main():
    # StringSession() без аргумента = пустая сессия в памяти: файл getter_bot.session
    # не трогаем, чтобы перевыпуск для CI не ломал локальную разработку.
    session = StringSession() if as_string else session_name
    client = TelegramClient(session, api_id, api_hash)
    # interactive: asks for phone -> login code (sent in Telegram) -> 2FA password
    await client.start()
    me = await client.get_me()
    print(f'OK [{"string" if as_string else session_name}], authorized as',
          getattr(me, 'username', None) or me.id)
    if as_string:
        print('\n--- TELEGRAM_SESSION (вставить в GitHub Secret целиком) ---')
        print(client.session.save())
        print('--- конец ---')
    await client.disconnect()


asyncio.run(main())
