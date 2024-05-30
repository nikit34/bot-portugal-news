

async def send_message_api(httpx_client, text, bot_token, chat_id):
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

    response = await httpx_client.get(url, params=params, headers=headers)
    response.raise_for_status()
