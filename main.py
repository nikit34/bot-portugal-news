from telethon import TelegramClient

from properties_reader import get_secret_key
from history_manager import get_messages_history


if __name__ == '__main__':

    api_id = get_secret_key('.', 'API_ID')
    api_hash = get_secret_key('.', 'API_HASH')
    password = get_secret_key('.', 'PASSWORD')
    bot_token = get_secret_key('.', 'TOKEN_BOT')
    chat_id = get_secret_key('.', 'CHAT_ID')

    client = TelegramClient('bot', api_id, api_hash)
    client.start(password=password, bot_token=bot_token)

    with client:
        history = get_messages_history(client, chat_id)
        client.loop.run_until_complete(history)
