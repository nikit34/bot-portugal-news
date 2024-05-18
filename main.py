from telethon import TelegramClient

from properties_reader import get_secret_key


if __name__ == '__main__':

    api_id = get_secret_key('.', 'API_ID')
    api_hash = get_secret_key('.', 'API_HASH')
    phone = get_secret_key('.', 'PHONE')
    password = get_secret_key('.', 'PASSWORD')
    bot_token = get_secret_key('.', 'TOKEN_BOT')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(phone=phone, password=password, bot_token=bot_token)


    async def main():
        await client.send_message('me', 'Hello to myself!')


    with client:
        client.loop.run_until_complete()