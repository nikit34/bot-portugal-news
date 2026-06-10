import asyncio
import os
import sys

from telethon import TelegramClient

session = sys.argv[1] if len(sys.argv) > 1 else 'getter_bot'
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']


async def main():
    client = TelegramClient(session, api_id, api_hash)
    # interactive: asks for phone -> login code (sent in Telegram) -> 2FA password
    await client.start()
    me = await client.get_me()
    print(f'OK [{session}], authorized as', getattr(me, 'username', None) or me.id)
    await client.disconnect()


asyncio.run(main())
