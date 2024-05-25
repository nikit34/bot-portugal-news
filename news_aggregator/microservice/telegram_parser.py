from collections import deque
from telethon import TelegramClient, events

from config import api_id, api_hash
from static.settings import KEY_SEARCH_LENGTH_CHARS


def telegram_parser(session, api_id, api_hash, telegram_channels, posted_q,
                    send_message_func=None, loop=None):
    '''Телеграм парсер'''

    # Ссылки на телеграмм каналы
    telegram_channels_links = list(telegram_channels.values())

    client = TelegramClient(session, api_id, api_hash,
                            loop=loop)
    client.start()

    @client.on(events.NewMessage(chats=telegram_channels_links))
    async def handler(event):
        '''Забирает посты из телеграмм каналов и посылает их в наш канал'''
        if event.raw_text == '':
            return

        news_text = ' '.join(event.raw_text.split('\n')[:2])

        head = news_text[:KEY_SEARCH_LENGTH_CHARS].strip()

        if head in posted_q:
            return

        source = telegram_channels[event.message.peer_id.channel_id]

        link = f'{source}/{event.message.id}'

        channel = '@' + source.split('/')[-1]

        post = f'<b>{channel}</b>\n{link}\n{news_text}'

        if send_message_func is None:
            print(post, '\n')
        else:
            await send_message_func(post)

        posted_q.appendleft(head)

    return client


if __name__ == "__main__":

    telegram_channels = {
        1099860397: 'https://t.me/rbc_news',
        1428717522: 'https://t.me/gazprom',
        1101170442: 'https://t.me/rian_ru',
        1133408457: 'https://t.me/prime1',
        1149896996: 'https://t.me/interfaxonline',
        # 1001029560: 'https://t.me/bcs_express',
        1203560567: 'https://t.me/markettwits',
    }

    # Очередь из уже опубликованных постов, чтобы их не дублировать
    posted_q = deque(maxlen=20)

    client = telegram_parser('gazp', api_id, api_hash, telegram_channels, posted_q)

    client.run_until_disconnected()