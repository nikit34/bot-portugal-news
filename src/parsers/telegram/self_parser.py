from src.processor.history_comparator import make_head


async def get_telegram_published_messages(getter_client, limit, context):
    history = []
    async for message in getter_client.iter_messages(context['self_telegram_channel'], limit=limit):
        raw_message = message.raw_text
        if not raw_message:
            continue
        history.append(make_head(raw_message))
    return history
