from collections import deque

from telethon import TelegramClient

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, COUNT_UNIQUE_MESSAGES
from static.sources import self_telegram_channel


async def get_messages_history(getter_client):
    history = []
    async for message in getter_client.iter_messages(self_telegram_channel, limit=COUNT_UNIQUE_MESSAGES):
        raw_message = message.raw_text
        if raw_message is None:
            continue
        post = raw_message.split('\n', maxsplit=1)[1]
        cropped_post = post[:KEY_SEARCH_LENGTH_CHARS].strip()
        history.append(cropped_post)
    return history


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    getter_client = TelegramClient('getter_bot', api_id, api_hash)
    getter_client.start(password=password, bot_token=bot_token)

    feature_history = get_messages_history(getter_client)
    history = getter_client.loop.run_until_complete(feature_history)
    posted_q.extend(history)
