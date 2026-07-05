import asyncio
from collections import deque

import pytest

import src.processor.service as svc
from src.static.sources import Platform


PLATFORMS = {Platform.ALL: None, Platform.FACEBOOK: True, Platform.INSTAGRAM: True, Platform.TELEGRAM: True}
CONTEXT = {
    'platforms': PLATFORMS,
    'self_instagram_channel': 'IG',
    'self_facebook_page_id': 'FB',
    'self_telegram_channel': 'tg',
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
    monkeypatch.setattr(svc, 'POST_DELAY_SECONDS', 0)
    # Stub image filters (avoid PIL/nudenet + real files) and prepare functions.
    monkeypatch.setattr(svc, 'is_low_quality_image', lambda p: False)
    monkeypatch.setattr(svc, 'is_unsafe_image', lambda p: False)
    monkeypatch.setattr(svc, 'facebook_prepare_post', lambda msg, doc: msg)
    monkeypatch.setattr(svc, 'instagram_prepare_post', lambda msg, doc: (msg, ''))
    monkeypatch.setattr(svc, 'telegram_prepare_post', lambda msg: msg)


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
    monkeypatch.setattr(svc, 'telegram_send_message', make(Platform.TELEGRAM))
    return calls


async def _serve(message='Benfica vence o Porto numa noite memoravel no estadio da luz', posted=None, source='abola.pt'):
    posted = deque() if posted is None else posted
    await svc.serve(None, object(), _nlp, _Translator(), message, _url_path, posted, CONTEXT, source=source)
    return posted


async def test_fresh_post_publishes_to_all_platforms(monkeypatch):
    calls = _mock_sends(monkeypatch)
    posted = await _serve()

    assert set(calls) == {Platform.FACEBOOK, Platform.INSTAGRAM, Platform.TELEGRAM}
    assert svc._published_count == 1
    assert svc._ig_posts_this_run == 1
    assert svc.get_run_stats()['platforms'] == {'FACEBOOK': 1, 'INSTAGRAM': 1, 'TELEGRAM': 1}
    assert len(svc.get_publish_records()) == 1 and svc.get_publish_records()[0]['source'] == 'abola.pt'
    # mark_posted recorded the head on all three platforms
    assert len(posted) == 1 and posted[0][1] == {Platform.FACEBOOK, Platform.INSTAGRAM, Platform.TELEGRAM}


async def test_duplicate_is_skipped(monkeypatch):
    calls = _mock_sends(monkeypatch)
    from src.processor.history_comparator import make_head
    head = make_head('Benfica vence o Porto numa noite memoravel no estadio da luz')
    posted = deque([[head, {Platform.FACEBOOK, Platform.INSTAGRAM, Platform.TELEGRAM}]])

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
    await svc.serve(None, object(), _nlp, _Translator(),
                    'Benfica vence o Porto numa noite memoravel no estadio da luz',
                    _no_file, posted, CONTEXT, source='t.me/x')

    assert calls == []
    assert svc._published_count == 0
    assert len(posted) == 0


async def test_meta_rate_limit_opens_circuit(monkeypatch):
    # FB rate-limited; IG+TG still publish, and the Meta circuit latches open.
    calls = _mock_sends(monkeypatch, fail={Platform.FACEBOOK: _RateLimited()})

    await _serve()

    assert svc._meta_circuit_open is True
    assert Platform.TELEGRAM in calls
    assert svc._published_count == 1  # IG/TG succeeded


async def test_ig_daily_quota_skips_instagram(monkeypatch):
    calls = _mock_sends(monkeypatch)
    svc.set_ig_daily(12, 12)  # quota spent

    await _serve()

    assert Platform.INSTAGRAM not in calls
    assert {Platform.FACEBOOK, Platform.TELEGRAM} <= set(calls)
    assert svc._ig_posts_this_run == 0


async def test_ranker_pools_in_phase1_then_drains(monkeypatch):
    # With the ranker ON, serve() pools candidates (publishes nothing); drain_pool
    # then publishes them. Flag OFF behaviour is covered by all the other tests.
    monkeypatch.setattr(svc, 'RANKER_ENABLED', True)
    monkeypatch.setattr(svc, 'RANKER_POOL_FACTOR', 4)
    svc._candidate_pool = []
    calls = _mock_sends(monkeypatch)

    posted = deque()
    await svc.serve(None, object(), _nlp, _Translator(),
                    'Benfica vence o Porto numa noite memoravel no estadio da luz',
                    _url_path, posted, CONTEXT, source='abola.pt')
    await svc.serve(None, object(), _nlp, _Translator(),
                    'Sporting empata fora e segue lider isolado na tabela da liga portuguesa',
                    _url_path, posted, CONTEXT, source='rtp.pt')

    assert calls == []                       # phase 1 publishes nothing
    assert len(svc._candidate_pool) == 2

    await svc.drain_pool(None, object(), _nlp, {'sources': {}, 'hours': {}})

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
    await svc.serve(None, object(), thin_nlp, _Translator(),
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
    await svc.serve(None, object(), thin_nlp, _Translator(),
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
    await svc.serve(None, object(), thin_nlp, _Translator(),
                    '🔥 Golo do Benfica!', _url_path, posted, CONTEXT, source='t.me/x')

    assert calls == []
    assert svc._candidate_pool == []            # gated, not pooled


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
