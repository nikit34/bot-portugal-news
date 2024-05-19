from collections import deque

from telethon import TelegramClient

from parsers.telegram import telegram_parser
from properties_reader import get_secret_key
from history_manager import get_messages_history
from static.settings import COUNT_UNIQUE_MESSAGES, KEY_SEARCH_LENGTH_CHARS


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

        posted_q = deque(maxlen=COUNT_UNIQUE_MESSAGES)

        client = telegram_parser(
            client=client,
            chat_id=chat_id,
            posted_q=posted_q
        )

        try:
            client.run_until_disconnected()
        except Exception as e:
            message = '&#9888; ERROR: Parsers is down\n' + str(e)
            feature = client.send_message(entity=chat_id, message=message, parse_mode='html', link_preview=False)
            client.loop.run_until_complete(feature)
