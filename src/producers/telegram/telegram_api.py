import logging
import httpx


logger = logging.getLogger('app')


async def send_message_api(text, telegram_bot_token, context):
    url = 'https://api.telegram.org/bot' + telegram_bot_token + '/sendMessage'

    params = {
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": False,
        "reply_to_message_id": None,
        "chat_id": context['self']['telegram_debug_chat_id']
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as httpx_client:
        try:
            response = await httpx_client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except Exception as e:
            logger.warning("Request 'send_message_api' failed: " + str(e))
