import asyncio
import logging
from time import sleep
from telethon.errors import FloodWaitError

from src.static.settings import REPEAT_REQUESTS, TIMEOUT
from src.utils.notify import redact_secrets


logger = logging.getLogger('app')


def is_rate_limited(e):
    code = getattr(e, 'code', None)
    if code in (4, 17, 32, 368, 613):
        return True
    text = (str(getattr(e, 'message', '') or '') + ' ' + str(e)).lower()
    markers = (
        'ограничива', 'защитить наше сообщество', 'спам',
        'rate limit', 'too many requests', 'reduce the amount',
        'temporarily blocked', 'action blocked', '#368',
    )
    return any(marker in text for marker in markers)


def log_error(func, attempts, args, e):
    response_content = ''
    if hasattr(e, 'response') and e.response is not None:
        try:
            response_content = e.response.content.decode('utf-8')
        except:
            response_content = str(e.response.content)
    
    logger.warning(redact_secrets(
        "Request '" + func.__name__ + "' failed, " +
        str(attempts) + "  attempts left, parameters: " + str(args) + ", error: " + str(e) +
        ", response: " + response_content
    ))


def async_retry(repeat=REPEAT_REQUESTS, timeout=TIMEOUT):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            attempts = repeat
            while attempts > 0:
                try:
                    return await func(*args, **kwargs)
                except FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"FloodWaitError: waiting {wait_time} seconds before retry")
                    await asyncio.sleep(wait_time)
                    return await func(*args, **kwargs)
                except Exception as e:
                    if is_rate_limited(e):
                        logger.warning("Rate limited on '" + func.__name__ + "', not retrying: " + str(e))
                        raise
                    attempts -= 1
                    if attempts > 0:
                        log_error(func, attempts, args, e)
                        await asyncio.sleep(timeout)
                    else:
                        raise
        return wrapper
    return decorator


def retry(repeat=REPEAT_REQUESTS, timeout=TIMEOUT):
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = repeat
            while attempts > 0:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if is_rate_limited(e):
                        logger.warning("Rate limited on '" + func.__name__ + "', not retrying: " + str(e))
                        raise
                    attempts -= 1
                    if attempts > 0:
                        log_error(func, attempts, args, e)
                        sleep(timeout)
                    else:
                        raise
        return wrapper
    return decorator
