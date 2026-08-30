import logging

from src.static.settings import (
    REDIS_ENABLED,
    REDIS_SOCKET_TIMEOUT_SECONDS,
    REDIS_URL,
)

app_logger = logging.getLogger('app')

_client = None
_unavailable = False


def is_enabled():
    """Redis настроен и ещё не отвалился на этом прогоне."""
    if _unavailable:
        return False
    if _client is not None:
        return True
    return bool(REDIS_ENABLED and REDIS_URL)


async def get_client():
    """Ленивое подключение. None => работаем по старой схеме, без Redis."""
    global _client
    if not is_enabled():
        return None
    if _client is not None:
        return _client
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            health_check_interval=30,
        )
        await client.ping()
    except Exception as e:
        mark_unavailable(e)
        return None
    _client = client
    app_logger.info("[redis] connected")
    return client


def mark_unavailable(error):
    """Гасим Redis до конца прогона: дальше всё идёт по деградированному пути."""
    global _unavailable
    if not _unavailable:
        app_logger.warning(f"[redis] disabled for this run: {error}")
    _unavailable = True


async def close():
    global _client
    if _client is None:
        return
    try:
        await _client.aclose()
    except Exception:
        app_logger.warning("[redis] error closing client", exc_info=True)
    _client = None


def reset():
    global _client, _unavailable
    _client = None
    _unavailable = False


def set_client(client):
    global _client, _unavailable
    _client = client
    _unavailable = False
