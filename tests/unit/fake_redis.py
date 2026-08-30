"""Минимальный in-memory аналог redis.asyncio для тестов store-слоя."""


def _slice(items, start, stop):
    n = len(items)
    if start < 0:
        start = max(n + start, 0)
    if stop < 0:
        stop = n + stop
    if stop < 0 or start > stop:
        return []
    return items[start:min(stop, n - 1) + 1]


class FakePipeline:
    def __init__(self, client):
        self._client = client
        self._queued = []

    def _queue(self, name, args, kwargs):
        self._queued.append((name, args, kwargs))
        return self

    def __getattr__(self, name):
        def call(*args, **kwargs):
            return self._queue(name, args, kwargs)
        return call

    async def execute(self):
        results = []
        for name, args, kwargs in self._queued:
            results.append(await getattr(self._client, name)(*args, **kwargs))
        self._queued = []
        return results


class FakeRedis:
    def __init__(self, fail=False):
        self.hashes = {}
        self.zsets = {}
        self.strings = {}
        self.fail = fail
        self.closed = False

    def _check(self):
        if self.fail:
            raise ConnectionError('fake redis is down')

    def pipeline(self):
        return FakePipeline(self)

    async def ping(self):
        self._check()
        return True

    async def aclose(self):
        self.closed = True

    async def get(self, key):
        self._check()
        return self.strings.get(key)

    async def set(self, key, value):
        self._check()
        self.strings[key] = str(value)
        return True

    async def hset(self, key, field, value):
        self._check()
        self.hashes.setdefault(key, {})[field] = value
        return 1

    async def hget(self, key, field):
        self._check()
        return self.hashes.get(key, {}).get(field)

    async def hmget(self, key, fields):
        self._check()
        stored = self.hashes.get(key, {})
        return [stored.get(field) for field in fields]

    async def hgetall(self, key):
        self._check()
        return dict(self.hashes.get(key, {}))

    async def hdel(self, key, *fields):
        self._check()
        stored = self.hashes.get(key, {})
        return sum(1 for field in fields if stored.pop(field, None) is not None)

    def _sorted(self, key):
        return sorted(self.zsets.get(key, {}).items(), key=lambda pair: (pair[1], pair[0]))

    async def zadd(self, key, mapping, nx=False):
        self._check()
        stored = self.zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if nx and member in stored:
                continue
            added += member not in stored
            stored[member] = score
        return added

    async def zrem(self, key, *members):
        self._check()
        stored = self.zsets.get(key, {})
        return sum(1 for member in members if stored.pop(member, None) is not None)

    async def zrange(self, key, start, stop):
        self._check()
        return [member for member, _ in _slice(self._sorted(key), start, stop)]

    async def zrevrange(self, key, start, stop):
        self._check()
        return [member for member, _ in _slice(list(reversed(self._sorted(key))), start, stop)]

    async def zcard(self, key):
        self._check()
        return len(self.zsets.get(key, {}))

    async def zremrangebyscore(self, key, low, high):
        self._check()
        low = float('-inf') if low == '-inf' else float(low)
        high = float('inf') if high == '+inf' else float(high)
        stored = self.zsets.get(key, {})
        doomed = [member for member, score in stored.items() if low <= score <= high]
        for member in doomed:
            del stored[member]
        return len(doomed)

    async def zremrangebyrank(self, key, start, stop):
        self._check()
        stored = self.zsets.get(key, {})
        doomed = [member for member, _ in _slice(self._sorted(key), start, stop)]
        for member in doomed:
            del stored[member]
        return len(doomed)
