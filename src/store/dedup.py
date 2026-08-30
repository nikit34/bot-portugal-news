import logging
import time
from collections import deque

from src.static.settings import (
    REDIS_DEDUP_ENABLED,
    REDIS_DEDUP_MAX_HEADS,
    REDIS_DEDUP_RESYNC_SECONDS,
    REDIS_DEDUP_TTL_SECONDS,
    REDIS_NAMESPACE,
)
from src.static.sources import Platform
from src.store import redis_client

app_logger = logging.getLogger('app')

_SEPARATOR = ','


def enabled():
    return REDIS_DEDUP_ENABLED and redis_client.is_enabled()


def _keys(config_name):
    base = f'{REDIS_NAMESPACE}:{config_name}:published'
    return base, f'{base}:index', f'{base}:synced_at'


def _decode(raw):
    platforms = set()
    for name in (raw or '').split(_SEPARATOR):
        name = name.strip()
        if name and hasattr(Platform, name):
            platforms.add(getattr(Platform, name))
    return platforms


def _encode(platforms):
    return _SEPARATOR.join(sorted(p.name for p in platforms))


async def _client(config_name):
    if not (REDIS_DEDUP_ENABLED and config_name):
        return None
    return await redis_client.get_client()


async def _trim(client, hash_key, index_key):
    await client.zremrangebyscore(index_key, '-inf', time.time() - REDIS_DEDUP_TTL_SECONDS)
    stale = await client.zrange(index_key, 0, -(REDIS_DEDUP_MAX_HEADS + 1))
    if stale:
        await client.hdel(hash_key, *stale)
        await client.zrem(index_key, *stale)


async def load(config_name):
    """Леджер опубликованного из Redis. None => данных нет, читаем историю площадок."""
    client = await _client(config_name)
    if client is None:
        return None
    hash_key, index_key, _ = _keys(config_name)
    try:
        await _trim(client, hash_key, index_key)
        heads = await client.zrevrange(index_key, 0, REDIS_DEDUP_MAX_HEADS - 1)
        if not heads:
            return None
        values = await client.hmget(hash_key, heads)
    except Exception as e:
        redis_client.mark_unavailable(e)
        return None

    posted = deque()
    for head, raw in zip(heads, values):
        platforms = _decode(raw)
        if platforms:
            posted.append([head, platforms])
    return posted or None


async def record(config_name, head, platforms):
    """Дописывает одну голову. Площадки объединяются с уже записанными."""
    client = await _client(config_name)
    if client is None or not head or not platforms:
        return False
    hash_key, index_key, _ = _keys(config_name)
    try:
        merged = _decode(await client.hget(hash_key, head)) | set(platforms)
        pipe = client.pipeline()
        pipe.hset(hash_key, head, _encode(merged))
        pipe.zadd(index_key, {head: time.time()})
        await pipe.execute()
        await _trim(client, hash_key, index_key)
    except Exception as e:
        redis_client.mark_unavailable(e)
        return False
    return True


async def seed(config_name, posted):
    """Заливает историю площадок в Redis одним пайплайном."""
    client = await _client(config_name)
    if client is None or not posted:
        return 0
    hash_key, index_key, synced_key = _keys(config_name)
    now = time.time()
    written = 0
    try:
        existing = await client.hgetall(hash_key)
        pipe = client.pipeline()
        for head, platforms in posted:
            if not head or not platforms:
                continue
            merged = _decode(existing.get(head)) | set(platforms)
            pipe.hset(hash_key, head, _encode(merged))
            pipe.zadd(index_key, {head: now}, nx=True)
            written += 1
        pipe.set(synced_key, str(now))
        await pipe.execute()
        await _trim(client, hash_key, index_key)
    except Exception as e:
        redis_client.mark_unavailable(e)
        return 0
    app_logger.info(f"[redis] seeded dedup ledger with {written} heads from platform history")
    return written


async def sync_due(config_name):
    """Пора ли снова сверить леджер с историей площадок (страховка от потери Redis)."""
    client = await _client(config_name)
    if client is None:
        return True
    if REDIS_DEDUP_RESYNC_SECONDS <= 0:
        return False
    _, _, synced_key = _keys(config_name)
    try:
        raw = await client.get(synced_key)
    except Exception as e:
        redis_client.mark_unavailable(e)
        return True
    try:
        last = float(raw)
    except (TypeError, ValueError):
        return True
    return (time.time() - last) >= REDIS_DEDUP_RESYNC_SECONDS
