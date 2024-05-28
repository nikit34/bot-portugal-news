from collections import deque

from googletrans import Translator
from telethon import TelegramClient, events

from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS
from static.sources import telegram_channels


def telegram_parser(getter_client, translator, chat_id, posted_q):
    telegram_channels_links = list(telegram_channels.values())

    @getter_client.on(events.NewMessage(chats=telegram_channels_links))
    async def handler(event):
        message = event.raw_text
        file = event.file

        if not message or file is None:
            return

        source = telegram_channels.get(event.message.peer_id.channel_id)
        link = source + '/' + str(event.message.id)
        channel = '@' + source.split('/')[-1]

        translated = translator.translate(message, dest='pt', src='ru')
        translated_message = translated.text

        head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()
        if head in posted_q:
            return
        posted_q.appendleft(head)

        post = '<a href="' + link + '">' + channel + '</a>\n' + message

        await getter_client.send_message(
            entity=int(chat_id),
            message=post,
            file=file.media,
            parse_mode='html',
            link_preview=False
        )

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

    translator = Translator(service_urls=['translate.googleapis.com'])

    getter_client = telegram_parser(getter_client=getter_client, translator=translator, chat_id=chat_id, posted_q=posted_q)
    getter_client.run_until_disconnected()
