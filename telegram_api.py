import httpx


async def send_message(text, bot_token, chat_id):
    url = 'https://api.telegram.org/bot' + bot_token + '/sendMessage'

    params = {
        'text': text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": False,
        "reply_to_message_id": None,
        "chat_id": str(chat_id)
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            status_code = response.status_code
    except Exception as e:
        print(e)
        status_code = 500
    return status_code
