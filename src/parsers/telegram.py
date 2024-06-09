from src.senders.telegram.sender import process_and_send_message
from src.static.settings import MAX_NUMBER_TAKEN_MESSAGES
from src.static.sources import telegram_channels
from src.senders.telegram.telegram_api import send_message_api


async def telegram_wrapper(getter_client, translator, bot_token, chat_id, debug_chat_id, channel, posted_q):
    try:
        await _telegram_parser(getter_client, translator, chat_id, channel, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: ' + channel + ' parser is down\n' + str(e)
        await send_message_api(message, bot_token, debug_chat_id)


async def _telegram_parser(getter_client, translator, chat_id, channel, posted_q):
    async for message in getter_client.iter_messages(channel, limit=MAX_NUMBER_TAKEN_MESSAGES):

        message_text = message.raw_text
        file = message.file

        if not message_text or file is None:
            continue

        source = telegram_channels.get(message.peer_id.channel_id)
        link = source + '/' + str(message.id)
        channel = '@' + source.split('/')[-1]

        await process_and_send_message(getter_client, translator, chat_id, posted_q, channel, message_text, link, file.media)
