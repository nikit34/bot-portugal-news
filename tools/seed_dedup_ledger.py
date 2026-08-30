#!/usr/bin/env python3
"""Разовая заливка дедуп-леджера в Redis из историй Facebook, Instagram и Telegram.

Обычный прогон бота истории площадок НЕ читает: «что уже опубликовано» живёт в
Redis. Этот скрипт нужен, когда леджера нет - первый запуск на новой базе, потеря
или пересоздание Redis. Без него бот в такой ситуации откажется публиковать,
потому что пустой леджер означает «мы ничего не постили» и прогон переопубликовал
бы всю ленту.

Ничего не публикует: только читает истории и пишет в Redis.

    REDIS_URL=rediss://... FACEBOOK_ACCESS_TOKEN=... TELEGRAM_SESSION=... \\
        python tools/seed_dedup_ledger.py
    ... python tools/seed_dedup_ledger.py --config food_br
"""
import os
import sys
import asyncio
import argparse

sys.path.insert(0, os.getcwd())

import facebook as fb                                               # noqa: E402
from telethon import TelegramClient                                 # noqa: E402
from telethon.sessions import StringSession                         # noqa: E402

from src.properties_reader import get_secret_key                    # noqa: E402
from src.static.sources import get_config, Platform                 # noqa: E402
from src.static.settings import COUNT_UNIQUE_MESSAGES               # noqa: E402
from src.parsers.facebook.self_parser import (                      # noqa: E402
    get_facebook_published_messages,
)
from src.parsers.instagram.self_parser import (                     # noqa: E402
    get_instagram_published_messages,
)
from src.parsers.telegram.self_parser import (                      # noqa: E402
    get_telegram_published_messages,
)
from src.processor.history_comparator import process_post_histories  # noqa: E402
from src.store import dedup, redis_client                           # noqa: E402


async def _empty():
    return []


def _resolve_page_token(graph, page_id):
    try:
        accounts = graph.get_connections('me', 'accounts', fields='id,access_token')
        for acc in accounts.get('data', []):
            if str(acc.get('id')) == str(page_id) and acc.get('access_token'):
                return acc['access_token']
    except Exception as e:
        print(f"page-token resolution failed ({e}); using the token as-is")
    return graph.access_token


async def seed(config_name, limit):
    context = get_config(config_name)

    if not dedup.enabled():
        print("REDIS_URL is not set (or the dedup ledger is disabled); nothing to seed")
        return 1

    graph = fb.GraphAPI(access_token=get_secret_key('.', 'FACEBOOK_ACCESS_TOKEN'))
    graph.access_token = _resolve_page_token(graph, context['self_facebook_page_id'])

    session = os.environ.get('TELEGRAM_SESSION')
    getter_client = TelegramClient(
        StringSession(session) if session else 'getter_bot',
        get_secret_key('.', 'TELEGRAM_API_ID'), get_secret_key('.', 'TELEGRAM_API_HASH'))
    await getter_client.start()

    try:
        telegram_enabled = Platform.TELEGRAM in context['platforms']
        facebook_history, instagram_history, telegram_history = await asyncio.gather(
            asyncio.to_thread(get_facebook_published_messages, graph, context, limit),
            asyncio.to_thread(get_instagram_published_messages, graph, context, limit),
            get_telegram_published_messages(getter_client, limit, context)
            if telegram_enabled else _empty(),
        )
        print(f"read history - Facebook: {len(facebook_history)}, "
              f"Instagram: {len(instagram_history)}, Telegram: {len(telegram_history)}")

        posted = process_post_histories(
            facebook_history, telegram_history, instagram_history)
        if not posted:
            print("no history read; refusing to seed an empty ledger")
            return 1

        written = await dedup.seed(config_name, posted)
        loaded = await dedup.load(config_name)
        print(f"seeded {written} heads; ledger now holds {len(loaded or [])}")
        return 0 if loaded else 1
    finally:
        await getter_client.disconnect()
        await redis_client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='football',
                        help='config name under src/static/configs (default: football)')
    parser.add_argument('--limit', type=int, default=COUNT_UNIQUE_MESSAGES,
                        help=f'posts to read per platform (default: {COUNT_UNIQUE_MESSAGES})')
    args = parser.parse_args()
    sys.exit(asyncio.run(seed(args.config, args.limit)))


if __name__ == '__main__':
    main()
