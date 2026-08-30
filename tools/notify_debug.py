#!/usr/bin/env python3
"""Сообщение в debug-чат из CI, когда сам прогон упал и питон уже ничего не скажет.

Внутри прогона уведомления шлёт send_debug_message тем же аккаунтом. Но если job
падает раньше (сборка окружения, таймаут, отменённый ран), сказать некому - для
этого шаг workflow с if: failure() зовёт этот скрипт.

    TELEGRAM_SESSION=... python tools/notify_debug.py --text 'CI упал' --url "$RUN_URL"
"""
import os
import sys
import asyncio
import argparse

sys.path.insert(0, os.getcwd())

from telethon import TelegramClient                                 # noqa: E402
from telethon.sessions import StringSession                         # noqa: E402

from src.properties_reader import get_secret_key                    # noqa: E402
from src.static.sources import get_config                           # noqa: E402
from src.producers.telegram.debug_chat import send_debug_message    # noqa: E402


async def notify(config_name, text, url):
    context = get_config(config_name)
    session = os.environ.get('TELEGRAM_SESSION')
    if not session:
        print("TELEGRAM_SESSION is not set; cannot notify")
        return 1

    client = TelegramClient(
        StringSession(session),
        get_secret_key('.', 'TELEGRAM_API_ID'), get_secret_key('.', 'TELEGRAM_API_HASH'))
    await client.start()
    try:
        message = text if not url else f'{text}\n\n<a href="{url}">Открыть логи CI</a>'
        await send_debug_message(message, client, context)
        print("notification sent")
        return 0
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='football')
    parser.add_argument('--text', required=True)
    parser.add_argument('--url', default='')
    args = parser.parse_args()
    sys.exit(asyncio.run(notify(args.config, args.text, args.url)))


if __name__ == '__main__':
    main()
