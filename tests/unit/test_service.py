import asyncio
from collections import deque, Counter

import pytest

import src.processor.service as svc
from src.static.sources import Platform


PLATFORMS = {Platform.ALL: None, Platform.FACEBOOK: True, Platform.INSTAGRAM: True}
CONTEXT = {
    'name': 'football',
    'platforms': PLATFORMS,
    'self_instagram_channel': 'IG',
    'self_facebook_page_id': 'FB',
}


class _Tok:
    is_stop = False
    is_punct = False
    text = 'w'


class _Doc:
    # Enough content tokens to clear MINIMUM_NUMBER_KEYWORDS in _low_semantic_load.
    def __init__(self, n=30):
        self._tokens = [_Tok() for _ in range(n)]
        self.ents = []

    def __iter__(self):
        return iter(self._tokens)


class _Translator:
    def translate(self, text):
        return text


def _nlp(_text):
    return _Doc()


class _RateLimited(Exception):
    code = 4  # is_rate_limited recognises codes in (4,17,32,368,613)


async def _url_path():
    return {'url': 'http://img/x.jpg', 'path': 'nonexistent.png'}


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # Reset all per-run module globals + rebind the lock to the test's event loop.
    svc._published_count = 0
    svc._meta_circuit_open = False
    svc._publish_records = []
    svc._run_cap = 3
    svc._ig_daily_count = 0
    svc._ig_daily_limit = 12
    svc._ig_posts_this_run = 0
    svc._deadline = None
    svc._platform_publishes = svc.Counter()
    svc._publish_lock = asyncio.Lock()
    svc._candidate_pool = []
    svc._pool_by_source = svc.Counter()
    svc._digest_mode = False
    monkeypatch.setattr(svc, 'POST_DELAY_SECONDS', 0)
    # Stub image filters (avoid PIL/nudenet + real files) and prepare functions.
    monkeypatch.setattr(svc, 'is_low_quality_image', lambda p: False)
    monkeypatch.setattr(svc, 'is_unsafe_image', lambda p: False)
    monkeypatch.setattr(svc, 'facebook_prepare_post', lambda msg, doc: msg)
    monkeypatch.setattr(svc, 'instagram_prepare_post', lambda msg, doc: (msg, ''))


def _mock_sends(monkeypatch, fail=()):
    calls = []

    def make(platform):
        async def send(*args, **kwargs):
            calls.append(platform)
            if platform in fail:
                raise fail[platform] if isinstance(fail, dict) else Exception('boom')
            return {'id': platform.name}
        return send

    monkeypatch.setattr(svc, 'facebook_send_message', make(Platform.FACEBOOK))
    monkeypatch.setattr(svc, 'instagram_send_message', make(Platform.INSTAGRAM))
    return calls


async def _serve(message='Benfica vence o Porto numa noite memoravel no estadio da luz', posted=None, source='abola.pt'):
    posted = deque() if posted is None else posted
    await svc.serve(object(), _nlp, _Translator(), message, _url_path, posted, CONTEXT, source=source)
    return posted


async def test_fresh_post_publishes_to_all_platforms(monkeypatch):
    calls = _mock_sends(monkeypatch)
    posted = await _serve()

    assert set(calls) == {Platform.FACEBOOK, Platform.INSTAGRAM}
    assert svc._published_count == 1
    assert svc._ig_posts_this_run == 1
    assert svc.get_run_stats()['platforms'] == {'FACEBOOK': 1, 'INSTAGRAM': 1}
    assert len(svc.get_publish_records()) == 1 and svc.get_publish_records()[0]['source'] == 'abola.pt'
    # mark_posted recorded the head on all three platforms
    assert len(posted) == 1 and posted[0][1] == {Platform.FACEBOOK, Platform.INSTAGRAM}


def _count_tags(monkeypatch):
    monkeypatch.setattr(svc, 'VARIANT_LOGGING_ENABLED', True)
    monkeypatch.setattr(svc, 'extract_hashtags',
                        lambda doc, max_count=svc.MAX_COUNT_KEYWORDS: ['t'] * max_count)


async def test_hashtag_n_records_the_facebook_capped_count(monkeypatch):
    _mock_sends(monkeypatch)
    _count_tags(monkeypatch)

    await _serve()

    assert svc.get_publish_records()[0]['hashtag_n'] == svc.HASHTAG_MAX_FB


async def test_hashtag_n_falls_back_to_default_cap_without_facebook(monkeypatch):
    _mock_sends(monkeypatch, fail={Platform.FACEBOOK: Exception('boom')})
    _count_tags(monkeypatch)

    await _serve()

    assert svc.get_publish_records()[0]['hashtag_n'] == svc.MAX_COUNT_KEYWORDS


async def test_duplicate_is_skipped(monkeypatch):
    calls = _mock_sends(monkeypatch)
    from src.processor.history_comparator import make_head
    head = make_head('Benfica vence o Porto numa noite memoravel no estadio da luz')
    posted = deque([[head, {Platform.FACEBOOK, Platform.INSTAGRAM}]])

    await _serve(posted=posted)

    assert calls == []
    assert svc._published_count == 0


async def test_budget_cap_blocks_publishing(monkeypatch):
    calls = _mock_sends(monkeypatch)
    svc._published_count = 3  # == _run_cap

    await _serve()

    assert calls == []


async def test_low_quality_image_skipped(monkeypatch):
    calls = _mock_sends(monkeypatch)
    monkeypatch.setattr(svc, 'is_low_quality_image', lambda p: True)

    await _serve()

    assert calls == []
    assert svc._published_count == 0


async def test_missing_media_path_is_skipped(monkeypatch):
    # Telegram media without a downloadable file (poll/geo/contact/dice) makes
    # download_media return None => url_path['path'] is None. Must skip cleanly,
    # not crash in _is_video on None.lower().
    calls = _mock_sends(monkeypatch)

    async def _no_file():
        return {'url': 'tg://media', 'path': None}

    posted = deque()
    await svc.serve(object(), _nlp, _Translator(),
                    'Benfica vence o Porto numa noite memoravel no estadio da luz',
                    _no_file, posted, CONTEXT, source='t.me/x')

    assert calls == []
    assert svc._published_count == 0
    assert len(posted) == 0


async def test_meta_rate_limit_opens_circuit(monkeypatch):
    calls = _mock_sends(monkeypatch, fail={Platform.FACEBOOK: _RateLimited()})

    await _serve()

    assert svc._meta_circuit_open is True
    assert Platform.INSTAGRAM in calls
    assert svc._published_count == 1


async def test_ig_daily_quota_skips_instagram(monkeypatch):
    calls = _mock_sends(monkeypatch)
    svc.set_ig_daily(12, 12)  # quota spent

    await _serve()

    assert Platform.INSTAGRAM not in calls
    assert Platform.FACEBOOK in calls
    assert svc._ig_posts_this_run == 0


async def test_ranker_pools_in_phase1_then_drains(monkeypatch):
    # With the ranker ON, serve() pools candidates (publishes nothing); drain_pool
    # then publishes them. Flag OFF behaviour is covered by all the other tests.
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 4)
    svc._candidate_pool = []
    calls = _mock_sends(monkeypatch)

    posted = deque()
    await svc.serve(object(), _nlp, _Translator(),
                    'Benfica vence o Porto numa noite memoravel no estadio da luz',
                    _url_path, posted, CONTEXT, source='abola.pt')
    await svc.serve(object(), _nlp, _Translator(),
                    'Sporting empata fora e segue lider isolado na tabela da liga portuguesa',
                    _url_path, posted, CONTEXT, source='rtp.pt')

    assert calls == []                       # phase 1 publishes nothing
    assert len(svc._candidate_pool) == 2

    await svc.drain_pool(object(), _nlp, {'sources': {}, 'hours': {}})

    assert svc._published_count >= 1          # phase 2 published
    assert svc._candidate_pool == []          # pool drained and cleared


async def test_low_semantic_load_gated_before_pooling(monkeypatch):
    # Regression: short/emoji-only posts (e.g. from headline-only Telegram channels)
    # must be dropped at phase-1 so they can't fill the ranker pool and starve the
    # run — which silently zeroed out all publishing for days.
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 4)
    svc._candidate_pool = []
    calls = _mock_sends(monkeypatch)
    thin_nlp = lambda _text: _Doc(n=1)  # 1 keyword < MINIMUM_NUMBER_KEYWORDS -> low load

    posted = deque()
    await svc.serve(object(), thin_nlp, _Translator(),
                    '🔥 FC Porto 🆚 Benfica', _url_path, posted, CONTEXT, source='t.me/x')

    assert calls == []                    # nothing published
    assert svc._candidate_pool == []      # and NOT pooled (would starve the run)


async def test_video_hint_exempts_low_semantic_gate_and_pools(monkeypatch):
    # A short-caption video clip (is_video_hint=True) must NOT be dropped by the
    # phase-1 text gate — its value is the clip, not the caption — and must be pooled
    # tagged is_video so the ranker can promote it. This is the keystone that lets
    # Telegram video actually reach publishing.
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 8)
    svc._candidate_pool = []
    calls = _mock_sends(monkeypatch)
    thin_nlp = lambda _text: _Doc(n=1)  # would trip the low-semantic gate for a photo

    posted = deque()
    await svc.serve(object(), thin_nlp, _Translator(),
                    '🔥 Golo do Benfica!', _url_path, posted, CONTEXT,
                    source='t.me/x', is_video_hint=True)

    assert calls == []                          # phase 1 publishes nothing
    assert len(svc._candidate_pool) == 1        # pooled despite tiny caption
    assert svc._candidate_pool[0]['is_video'] is True


async def test_photo_still_gated_without_hint(monkeypatch):
    # Control: same tiny caption WITHOUT the video hint stays gated (regression guard
    # for the pool-starvation fix — non-video short posts must not fill the pool).
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 8)
    svc._candidate_pool = []
    calls = _mock_sends(monkeypatch)
    thin_nlp = lambda _text: _Doc(n=1)

    posted = deque()
    await svc.serve(object(), thin_nlp, _Translator(),
                    '🔥 Golo do Benfica!', _url_path, posted, CONTEXT, source='t.me/x')

    assert calls == []
    assert svc._candidate_pool == []            # gated, not pooled


async def test_recipe_only_config_drops_unchecked_post(monkeypatch):
    # Канал по кухне (recipe_only): serve публикует только то, что источник пометил
    # recipe_checked. Путь без гейта не должен доносить пост до FB/IG (fail-closed).
    calls = _mock_sends(monkeypatch)
    context = {**CONTEXT, 'recipe_only': True}

    await svc.serve(object(), _nlp, _Translator(), 'Chef abre novo restaurante no Porto',
                    _url_path, deque(), context, source='rss')

    assert calls == []
    assert svc._published_count == 0


async def test_recipe_only_config_publishes_checked_post(monkeypatch):
    calls = _mock_sends(monkeypatch)
    context = {**CONTEXT, 'recipe_only': True}

    await svc.serve(object(), _nlp, _Translator(), 'Bolo de cenoura fofinho: ingredientes e modo de preparo',
                    _url_path, deque(), context, source='rss', recipe_checked=True)

    assert set(calls) == {Platform.FACEBOOK, Platform.INSTAGRAM}
    assert svc._published_count == 1


async def test_recipe_gate_does_not_touch_other_configs(monkeypatch):
    # У футбольного конфига recipe_only нет — recipe_checked не требуется.
    calls = _mock_sends(monkeypatch)

    await _serve()

    assert set(calls) == {Platform.FACEBOOK, Platform.INSTAGRAM}


async def test_should_stop_on_budget_and_deadline():
    svc._published_count = 0
    svc._run_cap = 3
    svc._deadline = None
    assert svc.should_stop() is False

    svc._published_count = 3  # budget filled
    assert svc.should_stop() is True

    svc._published_count = 0
    svc.set_deadline(0.0)  # monotonic deadline already in the past
    assert svc.time_budget_exceeded() is True
    assert svc.should_stop() is True


# --- режим дайджеста: один длинный ролик вместо N перепостов -----------------

# Заголовки нарочно НЕПОХОЖИ друг на друга: mark_posted/_find_posted матчат головы
# нечётко (порог схожести 0.7), и 'head0'/'head1' схлопнулись бы в одну запись.
_DIGEST_HEADS = ['Benfica vence classico', 'Sporting empata fora de casa',
                 'Porto contrata avancado brasileiro', 'Braga muda de treinador',
                 'Selecao convoca vinte tres jogadores', 'Arbitragem sob investigacao']


def _digest_candidates(n=6, is_video=False, offset=0):
    posted = deque()
    return [{
        'head': _DIGEST_HEADS[(offset + i) % len(_DIGEST_HEADS)], 'source': f'src{i}',
        'text': f'Notícia {i} do campeonato',
        'handler_url_path': _url_path, 'posted_d': posted, 'context': CONTEXT,
        'is_video': is_video,
    } for i in range(n)]


def _stub_digest(monkeypatch, video_path='/tmp/digest.mp4', headlines=None):
    seen = {}

    def fake_build(items, out_mp4=None):
        seen['items'] = items
        return (video_path, headlines if headlines is not None else
                [f'h{i}' for i in range(len(items))]) if video_path else (None, [])

    monkeypatch.setattr(svc, 'build_digest_video', fake_build)
    return seen


async def test_digest_publishes_single_long_video(monkeypatch):
    calls = _mock_sends(monkeypatch)
    seen = _stub_digest(monkeypatch)
    svc._candidate_pool = _digest_candidates()

    await svc.drain_digest(object(), _nlp, {}, CONTEXT)

    # ОДНА публикация вместо шести перепостов
    assert svc._published_count == 1
    assert calls.count(Platform.FACEBOOK) == 1
    assert Platform.INSTAGRAM not in calls        # IG за просмотры почти не платит
    assert len(seen['items']) == 6
    assert svc._candidate_pool == []


async def test_digest_record_is_isolated_from_source_learning(monkeypatch):
    _mock_sends(monkeypatch)
    _stub_digest(monkeypatch)
    svc._candidate_pool = _digest_candidates()

    await svc.drain_digest(object(), _nlp, {}, CONTEXT)

    record = svc.get_publish_records()[0]
    assert record['is_digest'] is True and record['source'] == 'digest'
    assert record['is_video'] is True
    assert record['fb_media_id'] == 'FACEBOOK'    # media-id под /video_insights


async def test_digest_skips_video_candidates(monkeypatch):
    # Чужой видеоклип внутрь ролика не вставляем — это вернуло бы неоригинальность,
    # ровно то, за что Meta снимает монетизацию.
    _mock_sends(monkeypatch)
    seen = _stub_digest(monkeypatch)
    svc._candidate_pool = _digest_candidates(3) + _digest_candidates(3, is_video=True)

    await svc.drain_digest(object(), _nlp, {}, CONTEXT)

    assert len(seen['items']) == 3


async def test_digest_not_published_when_render_fails(monkeypatch):
    calls = _mock_sends(monkeypatch)
    _stub_digest(monkeypatch, video_path=None)
    svc._candidate_pool = _digest_candidates()

    await svc.drain_digest(object(), _nlp, {}, CONTEXT)

    assert calls == []
    assert svc._published_count == 0
    assert svc._candidate_pool == []              # пул всё равно очищен


async def test_digest_marks_used_stories_posted(monkeypatch):
    _mock_sends(monkeypatch)
    _stub_digest(monkeypatch)
    candidates = _digest_candidates(5)
    posted = candidates[0]['posted_d']      # drain_digest очищает сам пул, ссылку берём заранее
    svc._candidate_pool = candidates

    await svc.drain_digest(object(), _nlp, {}, CONTEXT)

    # сюжеты, ушедшие в ролик, помечены — в этом же прогоне их не выложат отдельно
    heads = {entry[0] for entry in posted}
    assert set(_DIGEST_HEADS[:5]) <= heads


async def test_digest_respects_open_meta_circuit(monkeypatch):
    calls = _mock_sends(monkeypatch)
    _stub_digest(monkeypatch)
    svc._meta_circuit_open = True
    svc._candidate_pool = _digest_candidates()

    await svc.drain_digest(object(), _nlp, {}, CONTEXT)

    assert calls == []


async def test_digest_mode_pools_regardless_of_ranker_flag(monkeypatch):
    # Обычный ранкер выключен, но в режиме дайджеста фаза 1 обязана копить пул,
    # иначе собирать ролик будет не из чего.
    monkeypatch.setattr(svc, 'RANKER_ENABLED', False)
    calls = _mock_sends(monkeypatch)
    svc.set_digest_mode(True)

    await _serve()

    assert calls == []                            # ничего не публикуем в фазе 1
    assert len(svc._candidate_pool) == 1


async def test_digest_mode_stops_scraping_at_pool_target(monkeypatch):
    monkeypatch.setattr(svc, 'DIGEST_ITEMS', 2)
    monkeypatch.setattr(svc, 'DIGEST_POOL_FACTOR', 2)
    svc.set_digest_mode(True)

    assert svc.should_stop() is False
    svc._candidate_pool = [{}] * 4                # == DIGEST_ITEMS * DIGEST_POOL_FACTOR
    assert svc.should_stop() is True


async def test_digest_mode_ignores_post_budget(monkeypatch):
    # В режиме дайджеста публикация одна, поэтому счётчик постов не должен
    # останавливать сбор кандидатов.
    svc.set_digest_mode(True)
    svc._published_count = 99
    svc._run_cap = 3

    assert svc.should_stop() is False


@pytest.fixture
def queue_redis():
    from src.store import redis_client
    from tests.unit.fake_redis import FakeRedis

    client = FakeRedis()
    redis_client.set_client(client)
    yield client
    redis_client.reset()


def _queued_candidate(head='Benfica vence classico', url='http://img/x.jpg'):
    from src.files_manager import SaveFileUrl

    return {'head': head, 'source': 'abola.pt', 'text': 'Noticia do campeonato',
            'handler_url_path': SaveFileUrl(url), 'is_video': False}


async def test_pooled_candidate_is_pushed_to_the_redis_queue(monkeypatch, queue_redis):
    from src.files_manager import SaveFileUrl
    from src.store import candidate_queue

    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)

    await svc.serve(object(), _nlp, _Translator(),
                    'Benfica vence o Porto numa noite memoravel no estadio da luz',
                    SaveFileUrl('http://img/x.jpg'), deque(), CONTEXT, source='abola.pt')

    assert len(svc._candidate_pool) == 1
    assert svc._candidate_pool[0]['queue_member']
    assert len(await candidate_queue.load('football', 10)) == 1


async def test_digest_mode_does_not_push_to_the_redis_queue(monkeypatch, queue_redis):
    from src.files_manager import SaveFileUrl
    from src.store import candidate_queue

    svc._digest_mode = True

    await svc.serve(object(), _nlp, _Translator(),
                    'Benfica vence o Porto numa noite memoravel no estadio da luz',
                    SaveFileUrl('http://img/x.jpg'), deque(), CONTEXT, source='abola.pt')

    assert len(svc._candidate_pool) == 1
    assert await candidate_queue.load('football', 10) == []


async def test_leftover_candidate_is_restored_on_the_next_run(monkeypatch, queue_redis):
    from src.store import candidate_queue

    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    await candidate_queue.push('football', _queued_candidate())

    drained = []

    async def fake_publish(graph, nlp, text, handler, posted, context, source, head):
        drained.append(head)

    monkeypatch.setattr(svc, '_download_and_publish', fake_publish)

    await svc.drain_pool(object(), _nlp, {'sources': {}, 'hours': {}},
                         context=CONTEXT, posted_d=deque())

    assert drained == ['Benfica vence classico']
    assert await candidate_queue.load('football', 10) == []


async def test_restored_candidate_already_published_is_dropped(monkeypatch, queue_redis):
    from src.store import candidate_queue

    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    await candidate_queue.push('football', _queued_candidate())

    drained = []

    async def fake_publish(*args, **kwargs):
        drained.append(args)

    monkeypatch.setattr(svc, '_download_and_publish', fake_publish)
    posted = deque([['Benfica vence classico', {Platform.FACEBOOK, Platform.INSTAGRAM}]])

    await svc.drain_pool(object(), _nlp, {'sources': {}, 'hours': {}},
                         context=CONTEXT, posted_d=posted)

    assert drained == []
    assert await candidate_queue.load('football', 10) == []


async def test_candidate_left_unpublished_stays_in_the_queue(monkeypatch, queue_redis):
    from src.store import candidate_queue

    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    svc._run_cap = 1
    await candidate_queue.push('football', _queued_candidate('Benfica vence classico'))
    await candidate_queue.push('football', _queued_candidate('Sporting empata fora de casa'))

    async def fake_publish(graph, nlp, text, handler, posted, context, source, head):
        svc._published_count += 1

    monkeypatch.setattr(svc, '_download_and_publish', fake_publish)

    await svc.drain_pool(object(), _nlp, {'sources': {}, 'hours': {}},
                         context=CONTEXT, posted_d=deque())

    left = await candidate_queue.load('football', 10)
    assert len(left) == 1


async def test_publishing_records_the_head_in_the_redis_ledger(monkeypatch, queue_redis):
    from src.store import dedup

    _mock_sends(monkeypatch)

    await _serve()

    loaded = await dedup.load('football')
    assert loaded is not None
    assert len(loaded) == 1


async def _pool_from(source, n, monkeypatch):
    posted = deque()
    for i in range(n):
        await svc.serve(object(), _nlp, _Translator(), _DIGEST_HEADS[i % len(_DIGEST_HEADS)],
                        _url_path, posted, CONTEXT, source=source)
    return posted


async def test_one_source_cannot_take_more_than_its_share_of_the_pool(monkeypatch):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 3)
    monkeypatch.setattr(svc, 'RANKER_SOURCE_SHARE', 0.34)
    svc._run_cap = 3
    _mock_sends(monkeypatch)

    await _pool_from('zerozero.pt', 6, monkeypatch)

    assert svc.source_cap() == 3
    assert len(svc._candidate_pool) == 3
    assert {c['source'] for c in svc._candidate_pool} == {'zerozero.pt'}


async def test_a_filled_source_stops_itself_but_not_the_others(monkeypatch):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 3)
    monkeypatch.setattr(svc, 'RANKER_SOURCE_SHARE', 0.34)
    svc._run_cap = 3
    _mock_sends(monkeypatch)

    await _pool_from('zerozero.pt', 6, monkeypatch)

    assert svc.should_stop('zerozero.pt') is True
    assert svc.should_stop('https://t.me/FCPorto_INF') is False
    assert svc.should_stop() is False


async def test_pool_reaches_several_sources_instead_of_only_the_first(monkeypatch):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 3)
    monkeypatch.setattr(svc, 'RANKER_SOURCE_SHARE', 0.34)
    svc._run_cap = 3
    _mock_sends(monkeypatch)

    posted = deque()
    for source in ('zerozero.pt', 'https://t.me/FCPorto_INF'):
        for i in range(6):
            if svc.should_stop(source):
                break
            await svc.serve(object(), _nlp, _Translator(),
                            f'{_DIGEST_HEADS[i % len(_DIGEST_HEADS)]} via {source}',
                            _url_path, posted, CONTEXT, source=source)

    by_source = Counter(c['source'] for c in svc._candidate_pool)
    assert set(by_source) == {'zerozero.pt', 'https://t.me/FCPorto_INF'}


async def test_share_of_zero_restores_the_single_source_pool(monkeypatch):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 3)
    monkeypatch.setattr(svc, 'RANKER_SOURCE_SHARE', 0)
    svc._run_cap = 3
    _mock_sends(monkeypatch)

    await _pool_from('zerozero.pt', 12, monkeypatch)

    assert svc.source_cap() == 0
    assert len(svc._candidate_pool) == 9
    assert svc.should_stop('zerozero.pt') is True


async def test_draining_clears_the_per_source_counter(monkeypatch):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_SOURCE_SHARE', 0.34)
    _mock_sends(monkeypatch)

    async def fake_publish(*args, **kwargs):
        pass

    monkeypatch.setattr(svc, '_download_and_publish', fake_publish)
    await _pool_from('zerozero.pt', 2, monkeypatch)
    assert svc._pool_by_source['zerozero.pt'] > 0

    await svc.drain_pool(object(), _nlp, {'sources': {}, 'hours': {}})

    assert svc._pool_by_source == Counter()


async def test_concurrent_serves_cannot_overshoot_the_pool(monkeypatch):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 2)
    monkeypatch.setattr(svc, 'RANKER_SOURCE_SHARE', 0)
    svc._run_cap = 2
    _mock_sends(monkeypatch)

    async def slow_push(config_name, candidate):
        await asyncio.sleep(0)
        return 'member'

    monkeypatch.setattr(svc.candidate_queue, 'push', slow_push)

    posted = deque()
    await asyncio.gather(*[
        svc.serve(object(), _nlp, _Translator(), f'{_DIGEST_HEADS[i % 6]} numero {i}',
                  _url_path, posted, CONTEXT, source='abola.pt')
        for i in range(12)])

    assert len(svc._candidate_pool) == svc._pool_target() == 4


async def test_concurrent_serves_cannot_overshoot_the_source_cap(monkeypatch):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 8)
    monkeypatch.setattr(svc, 'RANKER_SOURCE_SHARE', 0.34)
    svc._run_cap = 2
    _mock_sends(monkeypatch)

    async def slow_push(config_name, candidate):
        await asyncio.sleep(0)
        return 'member'

    monkeypatch.setattr(svc.candidate_queue, 'push', slow_push)

    posted = deque()
    await asyncio.gather(*[
        svc.serve(object(), _nlp, _Translator(), f'{_DIGEST_HEADS[i % 6]} numero {i}',
                  _url_path, posted, CONTEXT, source='zerozero.pt')
        for i in range(15)])

    assert svc._pool_by_source['zerozero.pt'] == svc.source_cap() == 5


async def test_drain_logs_the_pool_mix_by_source(monkeypatch, caplog):
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    _mock_sends(monkeypatch)

    async def fake_publish(*args, **kwargs):
        pass

    monkeypatch.setattr(svc, '_download_and_publish', fake_publish)
    svc._candidate_pool = [
        {'head': h, 'source': src, 'text': 't', 'handler_url_path': _url_path,
         'posted_d': deque(), 'context': CONTEXT, 'is_video': False}
        for h, src in (('Benfica vence classico', 'zerozero.pt'),
                       ('Sporting empata fora de casa', 'zerozero.pt'),
                       ('Porto contrata avancado brasileiro', 'https://t.me/FCPorto_INF'))]

    with caplog.at_level('INFO', logger='app'):
        await svc.drain_pool(object(), _nlp, {'sources': {}, 'hours': {}})

    line = next(m for m in caplog.messages if 'pooled candidates by score' in m)
    assert 'zerozero.pt:2' in line
    assert 'https://t.me/FCPorto_INF:1' in line
