import asyncio
from collections import deque
from telethon import TelegramClient, events

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS
from static.sources import telegram_channels


def telegram_parser(client, chat_id, posted_q, key=KEY_SEARCH_LENGTH_CHARS):
    telegram_channels_links = list(telegram_channels.values())

    @client.on(events.NewMessage(chats=telegram_channels_links))
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

        await client.send_message(entity=int(chat_id), message=post, parse_mode='html', link_preview=False)

        posted_q.appendleft(head)
    return client


if __name__ == "__main__":
    api_id = get_secret_key('..', 'API_ID')
    api_hash = get_secret_key('..', 'API_HASH')
    password = get_secret_key('..', 'PASSWORD')
    bot_token = get_secret_key('..', 'TOKEN_BOT')
    chat_id = get_secret_key('..', 'CHAT_ID')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = TelegramClient('bot', api_id, api_hash, loop=loop)
    client.start(password=password, bot_token=bot_token)

    posted_q = deque(maxlen=20)

    with client:
        client = telegram_parser(client=client, chat_id=chat_id, posted_q=posted_q)
        client.run_until_disconnected()
