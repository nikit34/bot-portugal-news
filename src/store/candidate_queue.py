import json
import logging
import time

from src.files_manager import SaveFileTelegram, SaveFileUrl, SaveVideoUrl
from src.static.settings import (
    REDIS_NAMESPACE,
    REDIS_QUEUE_ENABLED,
    REDIS_QUEUE_MAX,
    REDIS_QUEUE_TTL_SECONDS,
)
from src.store import redis_client

app_logger = logging.getLogger('app')


def enabled():
    return REDIS_QUEUE_ENABLED and redis_client.is_enabled()


def _key(config_name):
    return f'{REDIS_NAMESPACE}:{config_name}:candidates'


async def _client(config_name):
    if not (REDIS_QUEUE_ENABLED and config_name):
        return None
    return await redis_client.get_client()


def serialize_media(handler, source):
    """Ссылка на медиа, переживающая прогон. None => кандидат не кладём в очередь."""
    if isinstance(handler, SaveVideoUrl):
        return {'kind': 'video_url', 'url': handler.url}
    if isinstance(handler, SaveFileUrl):
        return {'kind': 'image_url', 'url': handler.url}
    if isinstance(handler, SaveFileTelegram):
        message_id = getattr(getattr(handler, 'message', None), 'id', None)
        if message_id is None or not source:
            return None
        return {'kind': 'telegram', 'chat': source, 'message_id': message_id}
    return None


async def rehydrate_media(media, getter_client):
    """Восстанавливает загрузчик из сериализованной ссылки. None => источник пропал."""
    kind = (media or {}).get('kind')
    if kind == 'video_url':
        return SaveVideoUrl(media['url'])
    if kind == 'image_url':
        return SaveFileUrl(media['url'])
    if kind != 'telegram' or getter_client is None:
        return None
    try:
        message = await getter_client.get_messages(media['chat'], ids=media['message_id'])
    except Exception as e:
        app_logger.debug(f"[redis] queued telegram media unavailable: {e}")
        return None
    if message is None or getattr(message, 'media', None) is None:
        return None
    return SaveFileTelegram(getter_client, message)


async def _trim(client, config_name):
    key = _key(config_name)
    await client.zremrangebyscore(key, '-inf', time.time() - REDIS_QUEUE_TTL_SECONDS)
    await client.zremrangebyrank(key, 0, -(REDIS_QUEUE_MAX + 1))


async def push(config_name, candidate):
    """Кладёт кандидата в очередь. Возвращает member для последующего remove."""
    client = await _client(config_name)
    if client is None:
        return None
    media = serialize_media(candidate.get('handler_url_path'), candidate.get('source'))
    if media is None:
        return None
    member = json.dumps({
        'head': candidate.get('head'),
        'source': candidate.get('source'),
        'text': candidate.get('text'),
        'is_video': bool(candidate.get('is_video')),
        'media': media,
    }, sort_keys=True, ensure_ascii=False)
    try:
        await client.zadd(_key(config_name), {member: time.time()})
        await _trim(client, config_name)
    except Exception as e:
        redis_client.mark_unavailable(e)
        return None
    return member


async def load(config_name, limit):
    """Свежие кандидаты, оставшиеся от прошлых прогонов. Ничего не удаляет."""
    client = await _client(config_name)
    if client is None or limit <= 0:
        return []
    try:
        await _trim(client, config_name)
        members = await client.zrevrange(_key(config_name), 0, limit - 1)
    except Exception as e:
        redis_client.mark_unavailable(e)
        return []

    payloads = []
    stale = []
    for member in members:
        try:
            payload = json.loads(member)
        except ValueError:
            stale.append(member)
            continue
        payload['member'] = member
        payloads.append(payload)
    if stale:
        await remove(config_name, stale)
    return payloads


async def remove(config_name, members):
    members = [member for member in members if member]
    if not members:
        return
    client = await _client(config_name)
    if client is None:
        return
    try:
        await client.zrem(_key(config_name), *members)
    except Exception as e:
        redis_client.mark_unavailable(e)


async def size(config_name):
    client = await _client(config_name)
    if client is None:
        return 0
    try:
        return await client.zcard(_key(config_name))
    except Exception as e:
        redis_client.mark_unavailable(e)
        return 0
