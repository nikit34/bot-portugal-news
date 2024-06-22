import logging
from time import sleep

from src.static.settings import REPEAT_REQUESTS, TIMEOUT


logger = logging.getLogger(__name__)


def async_retry(repeat=REPEAT_REQUESTS, timeout=TIMEOUT):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            attempts = repeat
            while attempts > 0:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempts -= 1
                    if attempts > 0:
                        logger.warning(
                            "Request '" + func.__name__ + "' failed, " +
                            str(attempts) + "  attempts left: " + str(e)
                        )
                        sleep(timeout)
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
                    attempts -= 1
                    if attempts > 0:
                        logger.warning(
                            "Request '" + func.__name__ + "' failed, " +
                            str(attempts) + "  attempts left: " + str(e)
                        )
                        sleep(timeout)
                    else:
                        raise
        return wrapper
    return decorator
