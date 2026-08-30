import time
from collections import deque

import pytest

from src.files_manager import SaveFileTelegram, SaveFileUrl, SaveVideoUrl
from src.static.sources import Platform
from src.store import candidate_queue, dedup, redis_client
from tests.unit.fake_redis import FakeRedis


CONFIG = 'football'


@pytest.fixture
def fake():
    client = FakeRedis()
    redis_client.set_client(client)
    yield client
    redis_client.reset()


@pytest.fixture(autouse=True)
def _reset_redis_module():
    redis_client.reset()
    yield
    redis_client.reset()


def _posted(*entries):
    return deque([[head, set(platforms)] for head, platforms in entries])


async def test_dedup_load_is_none_without_redis():
    assert await dedup.load(CONFIG) is None
    assert dedup.enabled() is False


async def test_dedup_seed_then_load_round_trips_platforms(fake):
    await dedup.seed(CONFIG, _posted(
        ('Benfica vence classico', {Platform.FACEBOOK, Platform.INSTAGRAM}),
        ('Porto contrata avancado', {Platform.INSTAGRAM}),
    ))

    loaded = await dedup.load(CONFIG)

    assert loaded is not None
    by_head = {head: platforms for head, platforms in loaded}
    assert by_head['Benfica vence classico'] == {Platform.FACEBOOK, Platform.INSTAGRAM}
    assert by_head['Porto contrata avancado'] == {Platform.INSTAGRAM}


async def test_dedup_load_is_none_on_empty_ledger(fake):
    assert await dedup.load(CONFIG) is None


async def test_dedup_record_merges_platforms(fake):
    await dedup.record(CONFIG, 'Sporting empata fora', {Platform.INSTAGRAM})
    await dedup.record(CONFIG, 'Sporting empata fora', {Platform.FACEBOOK})

    loaded = await dedup.load(CONFIG)

    assert dict(loaded)['Sporting empata fora'] == {Platform.INSTAGRAM, Platform.FACEBOOK}


async def test_dedup_seed_does_not_drop_platforms_already_recorded(fake):
    await dedup.record(CONFIG, 'Braga muda de treinador', {Platform.INSTAGRAM})

    await dedup.seed(CONFIG, _posted(('Braga muda de treinador', {Platform.FACEBOOK})))

    assert dict(await dedup.load(CONFIG))['Braga muda de treinador'] == {
        Platform.INSTAGRAM, Platform.FACEBOOK}


async def test_dedup_trims_beyond_max_heads(fake, monkeypatch):
    monkeypatch.setattr(dedup, 'REDIS_DEDUP_MAX_HEADS', 3)

    for i in range(6):
        await dedup.record(CONFIG, f'head {i}', {Platform.FACEBOOK})

    loaded = await dedup.load(CONFIG)

    assert [head for head, _ in loaded] == ['head 5', 'head 4', 'head 3']
    hash_key, _, _ = dedup._keys(CONFIG)
    assert set(fake.hashes[hash_key]) == {'head 5', 'head 4', 'head 3'}


async def test_dedup_drops_heads_older_than_ttl(fake, monkeypatch):
    await dedup.record(CONFIG, 'noticia antiga', {Platform.FACEBOOK})
    _, index_key, _ = dedup._keys(CONFIG)
    fake.zsets[index_key]['noticia antiga'] = time.time() - 10_000

    monkeypatch.setattr(dedup, 'REDIS_DEDUP_TTL_SECONDS', 100)

    assert await dedup.load(CONFIG) is None


async def test_dedup_falls_back_when_redis_breaks_mid_run(fake):
    await dedup.record(CONFIG, 'Arbitragem sob investigacao', {Platform.FACEBOOK})
    fake.fail = True

    assert await dedup.load(CONFIG) is None
    assert redis_client.is_enabled() is False
    assert dedup.enabled() is False


async def test_queue_push_and_load_round_trip(fake):
    member = await candidate_queue.push(CONFIG, {
        'head': 'Benfica vence classico', 'source': 'abola.pt', 'text': 'texto',
        'handler_url_path': SaveFileUrl('http://img/x.jpg'), 'is_video': False,
    })

    assert member
    [payload] = await candidate_queue.load(CONFIG, 10)
    assert payload['head'] == 'Benfica vence classico'
    assert payload['media'] == {'kind': 'image_url', 'url': 'http://img/x.jpg'}
    assert payload['member'] == member


async def test_queue_load_returns_newest_first(fake):
    for i in range(3):
        await candidate_queue.push(CONFIG, {
            'head': f'head {i}', 'source': 'abola.pt', 'text': 't',
            'handler_url_path': SaveFileUrl(f'http://img/{i}.jpg'), 'is_video': False,
        })

    payloads = await candidate_queue.load(CONFIG, 10)

    assert [p['head'] for p in payloads] == ['head 2', 'head 1', 'head 0']


async def test_queue_skips_candidates_without_reusable_media(fake):
    async def handler():
        return {'path': 'x.png'}

    assert await candidate_queue.push(CONFIG, {
        'head': 'h', 'source': 'abola.pt', 'text': 't',
        'handler_url_path': handler, 'is_video': False,
    }) is None
    assert await candidate_queue.load(CONFIG, 10) == []


async def test_queue_remove_deletes_the_member(fake):
    member = await candidate_queue.push(CONFIG, {
        'head': 'h', 'source': 'abola.pt', 'text': 't',
        'handler_url_path': SaveVideoUrl('http://v/x.mp4'), 'is_video': True,
    })

    await candidate_queue.remove(CONFIG, [member])

    assert await candidate_queue.load(CONFIG, 10) == []


async def test_queue_drops_entries_older_than_ttl(fake, monkeypatch):
    member = await candidate_queue.push(CONFIG, {
        'head': 'h', 'source': 'abola.pt', 'text': 't',
        'handler_url_path': SaveFileUrl('http://img/x.jpg'), 'is_video': False,
    })
    fake.zsets[candidate_queue._key(CONFIG)][member] = time.time() - 10_000
    monkeypatch.setattr(candidate_queue, 'REDIS_QUEUE_TTL_SECONDS', 100)

    assert await candidate_queue.load(CONFIG, 10) == []


async def test_queue_keeps_only_the_newest_entries_over_the_cap(fake, monkeypatch):
    monkeypatch.setattr(candidate_queue, 'REDIS_QUEUE_MAX', 2)

    for i in range(4):
        await candidate_queue.push(CONFIG, {
            'head': f'head {i}', 'source': 'abola.pt', 'text': 't',
            'handler_url_path': SaveFileUrl(f'http://img/{i}.jpg'), 'is_video': False,
        })

    payloads = await candidate_queue.load(CONFIG, 10)

    assert [p['head'] for p in payloads] == ['head 3', 'head 2']


async def test_queue_serializes_telegram_media_by_chat_and_message_id():
    class _Message:
        id = 42

    media = candidate_queue.serialize_media(
        SaveFileTelegram(object(), _Message()), 'https://t.me/futebol_portugues')

    assert media == {'kind': 'telegram', 'chat': 'https://t.me/futebol_portugues',
                     'message_id': 42}


async def test_queue_rehydrates_url_media_without_a_telegram_client():
    handler = await candidate_queue.rehydrate_media(
        {'kind': 'video_url', 'url': 'http://v/x.mp4'}, None)

    assert isinstance(handler, SaveVideoUrl)
    assert handler.url == 'http://v/x.mp4'


async def test_queue_rehydrates_telegram_media_from_the_stored_id():
    class _Message:
        id = 7
        media = object()

    class _Getter:
        def __init__(self):
            self.asked = None

        async def get_messages(self, chat, ids):
            self.asked = (chat, ids)
            return _Message()

    getter = _Getter()
    handler = await candidate_queue.rehydrate_media(
        {'kind': 'telegram', 'chat': 'https://t.me/c', 'message_id': 7}, getter)

    assert isinstance(handler, SaveFileTelegram)
    assert getter.asked == ('https://t.me/c', 7)


async def test_queue_rehydration_returns_none_for_a_deleted_message():
    class _Getter:
        async def get_messages(self, chat, ids):
            return None

    assert await candidate_queue.rehydrate_media(
        {'kind': 'telegram', 'chat': 'https://t.me/c', 'message_id': 7}, _Getter()) is None


async def test_queue_survives_a_broken_redis(fake):
    fake.fail = True

    assert await candidate_queue.push(CONFIG, {
        'head': 'h', 'source': 'abola.pt', 'text': 't',
        'handler_url_path': SaveFileUrl('http://img/x.jpg'), 'is_video': False,
    }) is None
    assert await candidate_queue.load(CONFIG, 10) == []


def test_publish_is_allowed_once_the_ledger_has_heads():
    assert dedup.publish_blocked(_posted(('h', {Platform.FACEBOOK})), True, False) == ''


def test_publish_is_blocked_when_redis_is_unavailable():
    assert dedup.publish_blocked(None, False, True) == 'Redis is unavailable'


def test_publish_is_blocked_on_an_empty_ledger_by_default():
    assert dedup.publish_blocked(None, True, False) == 'the Redis dedup ledger is empty'


def test_empty_ledger_is_allowed_only_with_the_explicit_opt_in():
    assert dedup.publish_blocked(None, True, True) == ''
