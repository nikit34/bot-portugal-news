from collections import deque

from telethon import TelegramClient

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, COUNT_UNIQUE_MESSAGES


async def get_messages_history(getter_client, chat_id, key=KEY_SEARCH_LENGTH_CHARS, count=COUNT_UNIQUE_MESSAGES):
    history = []
    messages = await getter_client.get_messages(int(chat_id), count)

    for message in messages:
        if message.raw_text is None:
            continue
        post = message.raw_text.replace('\n', '')
        cropped_post = post[:key].strip()
        history.append(cropped_post)
    return history


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')
    chat_id = get_secret_key('..', 'CHAT_ID')

    posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

    getter_client = TelegramClient('getter_bot', api_id, api_hash)
    getter_client.start()

    feature_history = get_messages_history(getter_client, chat_id)
    history = getter_client.loop.run_until_complete(feature_history)
    posted_q.extend(history)
