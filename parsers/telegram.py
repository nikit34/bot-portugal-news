from collections import deque

from googletrans import Translator
from telethon import TelegramClient

from history_comparator import compare_messages
from properties_reader import get_secret_key
from static.settings import KEY_SEARCH_LENGTH_CHARS, COUNT_UNIQUE_MESSAGES, MAX_LENGTH_MESSAGE
from static.sources import telegram_channels
from text_editor import trunc_str


async def telegram_parser(getter_client, translator, chat_id, posted_q):
    telegram_channels_chat_ids = list(telegram_channels.keys())

    for telegram_channels_chat_id in telegram_channels_chat_ids:
        messages = await getter_client.get_messages(int(telegram_channels_chat_id), COUNT_UNIQUE_MESSAGES)

        for message in messages:

            message_text = message.raw_text
            file = message.file

            if not message_text or file is None:
                continue

            source = telegram_channels.get(message.peer_id.channel_id)
            link = source + '/' + str(message.id)
            channel = '@' + source.split('/')[-1]

            translated = translator.translate(message_text, dest='pt', src='ru')
            translated_message = translated.text

            head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()
            if compare_messages(head, posted_q):
                continue
            posted_q.appendleft(head)

            title_post = '<a href="' + link + '">' + channel + '</a>\n'
            post = title_post + trunc_str(translated_message, MAX_LENGTH_MESSAGE)

            await getter_client.send_message(
                entity=int(chat_id),
                message=post,
                file=file.media,
                parse_mode='html',
                link_preview=False
            )


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
