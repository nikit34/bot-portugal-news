from src.static.settings import MAX_ERROR_RESPONSE_CHARS


def build_error_message(summary, error, run_url):
    """Build a Telegram-safe error notification.

    The upstream response body is truncated so the message stays under Telegram's
    sendMessage length limit (4096 chars). A full HTML error page would otherwise
    blow past that limit and the alert itself would fail with 400 Bad Request,
    never reaching the chat.
    """
    response = getattr(error, 'response', None)
    response_text = ''
    if response is not None:
        body = (getattr(response, 'text', '') or '')[:MAX_ERROR_RESPONSE_CHARS]
        if body:
            response_text = f', response: {body}'

    message = f'{summary}\n{str(error)}{response_text}'
    if run_url:
        message += f'\n<a href="{run_url}">Open CI logs</a>'
    return message
