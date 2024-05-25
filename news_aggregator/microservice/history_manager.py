from static.settings import KEY_SEARCH_LENGTH_CHARS, COUNT_UNIQUE_MESSAGES


async def get_messages_history(client, chat_id, key=KEY_SEARCH_LENGTH_CHARS, count=COUNT_UNIQUE_MESSAGES):
    history = []
    messages = await client.get_messages(int(chat_id), count)

    for message in messages:
        if message.raw_text is None:
            continue
        post = message.raw_text.replace('\n', '')
        cropped_post = post[:key].strip()
        history.append(cropped_post)
    return history
