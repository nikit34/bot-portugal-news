from history_comparator import compare_messages
from static.settings import KEY_SEARCH_LENGTH_CHARS, MAX_LENGTH_MESSAGE, MAX_NUMBER_TAKEN_MESSAGES
from static.sources import telegram_channels
from telegram_api import send_message_api
from text_editor import trunc_str


async def telegram_wrapper(getter_client, translator, bot_token, chat_id, debug_chat_id, httpx_client, channel, posted_q):
    try:
        await _telegram_parser(getter_client, translator, chat_id, channel, posted_q)
    except Exception as e:
        message = '&#9888; ERROR: ' + channel + ' parser is down\n' + str(e)
        await send_message_api(httpx_client, message, bot_token, debug_chat_id)


async def _telegram_parser(getter_client, translator, chat_id, channel, posted_q):
    async for message in getter_client.iter_messages(channel, limit=MAX_NUMBER_TAKEN_MESSAGES):

        message_text = message.raw_text
        file = message.file

        if not message_text or file is None:
            continue

        source = telegram_channels.get(message.peer_id.channel_id)
        link = source + '/' + str(message.id)
        channel = '@' + source.split('/')[-1]

        translated = translator.translate(message_text, dest='pt')
        translated_message = translated.text

        head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()
        if compare_messages(head, posted_q):
            continue
        posted_q.appendleft(head)

        title_post = '<a href="' + link + '">' + channel + '</a>\n'
        post = title_post + trunc_str(translated_message, MAX_LENGTH_MESSAGE)

        message_sent = await getter_client.send_message(
            entity=int(chat_id),
            message=post,
            file=file.media,
            parse_mode='html',
            link_preview=False
        )
        second_translated_message = translator.translate(translated_message, dest='ru')
        await message_sent.respond('🇷🇺 ' + trunc_str(second_translated_message.text, MAX_LENGTH_MESSAGE), comment_to=message_sent.id)
