from src.static.settings import KEY_SEARCH_LENGTH_CHARS
from src.static.sources import self_telegram_channel


async def get_published_messages(getter_client, limit):
    history = []
    async for message in getter_client.iter_messages(self_telegram_channel, limit=limit):
        raw_message = message.raw_text
        if not raw_message:
            continue
        lines = raw_message.split('\n', maxsplit=1)
        if len(lines) < 2:
            continue
        post = lines[1]
        cropped_post = post[:KEY_SEARCH_LENGTH_CHARS].strip()
        history.append(cropped_post)
    return history
