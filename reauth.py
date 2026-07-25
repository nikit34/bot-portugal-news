"""Перевыпуск Telegram-сессии ЧИТАЮЩЕГО аккаунта (getter_bot).

CI авторизуется секретом TELEGRAM_SESSION. Когда Telegram эту сессию отзывает,
telethon в CI молча уходит в интерактивный логин и прогон падает с EOFError
(«Please enter your phone»), т.е. бот перестаёт публиковать ВООБЩЕ.

Режимы:

  1) Интерактивный — нужен НАСТОЯЩИЙ терминал (telethon читает stdin):

        venv/bin/python reauth.py                # файловая сессия getter_bot.session
        venv/bin/python reauth.py --string       # печатает StringSession для CI

  2) Двухшаговый БЕЗ терминала — для агентов/CI-шеллов, где stdin не TTY:

        venv/bin/python reauth.py --request --phone +351912345678
        # код придёт в Telegram
        venv/bin/python reauth.py --code 12345 [--password 2FA]

     Шаг 1 сохраняет предавторизационную сессию и phone_code_hash в файл
     состояния, шаг 2 логинится и ПИШЕТ готовую строку в файл (не печатает её:
     строка сессии = полный доступ к аккаунту).

Пути файлов переопределяются: REAUTH_STATE (состояние между шагами) и
REAUTH_OUT (куда положить итоговую строку). По умолчанию — во временный каталог,
НЕ в репозиторий, чтобы секрет нельзя было случайно закоммитить.

api_id/hash берутся как в main.py: env, иначе файл secret.
"""
import os
import sys
import json
import asyncio
import tempfile
import argparse

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from src.properties_reader import get_secret_key

_TMP = tempfile.gettempdir()
STATE_PATH = os.environ.get('REAUTH_STATE', os.path.join(_TMP, 'reauth_state.json'))
OUT_PATH = os.environ.get('REAUTH_OUT', os.path.join(_TMP, 'telegram_session.txt'))


def _credentials():
    return int(get_secret_key('.', 'TELEGRAM_API_ID')), get_secret_key('.', 'TELEGRAM_API_HASH')


def _optional_password(explicit):
    if explicit:
        return explicit
    try:
        return get_secret_key('.', 'TELEGRAM_PASSWORD')
    except KeyError:
        return None


async def interactive(session_name, as_string):
    api_id, api_hash = _credentials()
    # StringSession() без аргумента = пустая сессия в памяти: файл getter_bot.session
    # не трогаем, чтобы перевыпуск для CI не ломал локальную разработку.
    client = TelegramClient(StringSession() if as_string else session_name, api_id, api_hash)
    await client.start()
    me = await client.get_me()
    print(f'OK, authorized as', getattr(me, 'username', None) or me.id)
    if as_string:
        print('\n--- TELEGRAM_SESSION (вставить в GitHub Secret целиком) ---')
        print(client.session.save())
        print('--- конец ---')
    await client.disconnect()


async def request_code(phone):
    api_id, api_hash = _credentials()
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    sent = await client.send_code_request(phone)
    # Сохраняем ИМЕННО предавторизационную сессию: в ней уже есть auth_key и DC,
    # без них второй шаг (в другом процессе) не сможет подтвердить код.
    with open(STATE_PATH, 'w') as f:
        json.dump({'session': client.session.save(), 'phone': phone,
                   'hash': sent.phone_code_hash}, f)
    os.chmod(STATE_PATH, 0o600)
    await client.disconnect()
    print(f'Код отправлен в Telegram на {phone}. Состояние: {STATE_PATH}')
    print('Дальше: venv/bin/python reauth.py --code <код> [--password <2FA>]')


async def submit_code(code, password):
    api_id, api_hash = _credentials()
    with open(STATE_PATH) as f:
        state = json.load(f)
    client = TelegramClient(StringSession(state['session']), api_id, api_hash)
    await client.connect()
    try:
        await client.sign_in(phone=state['phone'], code=code, phone_code_hash=state['hash'])
    except SessionPasswordNeededError:
        password = _optional_password(password)
        if not password:
            print('У аккаунта включена 2FA: повторите с --password <пароль> '
                  '(или положите TELEGRAM_PASSWORD в env / файл secret)')
            await client.disconnect()
            sys.exit(2)
        await client.sign_in(password=password)

    me = await client.get_me()
    session_string = client.session.save()
    await client.disconnect()

    with open(OUT_PATH, 'w') as f:
        f.write(session_string)
    os.chmod(OUT_PATH, 0o600)
    os.remove(STATE_PATH)
    # Саму строку НЕ печатаем: это полный доступ к аккаунту.
    print(f'OK, authorized as', getattr(me, 'username', None) or me.id)
    print(f'Строка сессии ({len(session_string)} символов) записана в {OUT_PATH}')
    print(f'Установить секрет: gh secret set TELEGRAM_SESSION < {OUT_PATH}')


def main():
    parser = argparse.ArgumentParser(description='Перевыпуск Telegram StringSession')
    parser.add_argument('session', nargs='?', default='getter_bot')
    parser.add_argument('--string', action='store_true', help='печатать StringSession (нужен TTY)')
    parser.add_argument('--request', action='store_true', help='шаг 1: запросить код')
    parser.add_argument('--phone', help='телефон для --request, напр. +351912345678')
    parser.add_argument('--code', help='шаг 2: код из Telegram')
    parser.add_argument('--password', help='пароль 2FA (если включён)')
    args = parser.parse_args()

    if args.request:
        if not args.phone:
            parser.error('--request требует --phone')
        asyncio.run(request_code(args.phone))
    elif args.code:
        asyncio.run(submit_code(args.code, args.password))
    else:
        asyncio.run(interactive(args.session, args.string))


if __name__ == '__main__':
    main()
