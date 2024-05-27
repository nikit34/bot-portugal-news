from collections import deque
from telethon import TelegramClient, events

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, COUNT_UNIQUE_MESSAGES
from static.sources import telegram_channels


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


def telegram_parser(getter_client, chat_id, posted_q, key=KEY_SEARCH_LENGTH_CHARS):
    telegram_channels_links = list(telegram_channels.values())

    @getter_client.on(events.NewMessage(chats=telegram_channels_links))
    async def handler(event):
        if event.raw_text == '':
            return

        message = event.raw_text

        head = message[:key].strip()
        if head in posted_q:
            return

        source = telegram_channels[event.message.peer_id.channel_id]
        link = source + '/' + str(event.message.id)
        channel = '@' + source.split('/')[-1]
        post = '<a href="' + link + '">' + channel + '</a>\n' + message

        await getter_client.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)

        posted_q.appendleft(head)
    return getter_client


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')
    chat_id = get_secret_key('..', 'CHAT_ID')

    posted_q = deque(maxlen=20)

    getter_client = TelegramClient('getter_bot', api_id, api_hash)
    getter_client.start()

    getter_client = telegram_parser(getter_client=getter_client, chat_id=chat_id, posted_q=posted_q)
    getter_client.run_until_disconnected()
