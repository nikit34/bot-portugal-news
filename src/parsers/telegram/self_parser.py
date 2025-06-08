from src.static.settings import KEY_SEARCH_LENGTH_CHARS
from src.static.sources import self_telegram_channel


async def get_telegram_published_messages(getter_client, limit):
    history = []
    async for message in getter_client.iter_messages(self_telegram_channel, limit=limit):
        raw_message = message.raw_text
        if not raw_message:
            continue
        cropped_post = raw_message[:KEY_SEARCH_LENGTH_CHARS].strip()
        history.append(cropped_post)
    return history
