import pytest

import src.parsers.insights as ins


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_should_report_insights_gates_on_hour(monkeypatch):
    monkeypatch.setattr(ins, 'INSIGHTS_REPORT_ENABLED', True)
    monkeypatch.setattr(ins, 'INSIGHTS_REPORT_HOUR', 8)

    assert ins.should_report_insights(current_hour=8) is True
    assert ins.should_report_insights(current_hour=9) is False


def test_should_report_insights_respects_disable(monkeypatch):
    monkeypatch.setattr(ins, 'INSIGHTS_REPORT_ENABLED', False)
    monkeypatch.setattr(ins, 'INSIGHTS_REPORT_HOUR', 8)

    assert ins.should_report_insights(current_hour=8) is False


def test_media_insights_ranks_by_engagement_and_limits_reach_calls(monkeypatch):
    media = [
        {'id': 'm_low', 'caption': 'low', 'media_type': 'IMAGE', 'like_count': 1, 'comments_count': 0},
        {'id': 'm_high', 'caption': 'high', 'media_type': 'REELS', 'like_count': 50, 'comments_count': 5},
        {'id': 'm_mid', 'caption': 'mid', 'media_type': 'IMAGE', 'like_count': 10, 'comments_count': 1},
    ]
    reach_calls = []

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'data': media})
        if url.endswith('/insights'):
            media_id = url[len(ins._GRAPH):].split('/')[0]
            reach_calls.append(media_id)
            return _FakeResponse({'data': [{'name': 'reach', 'values': [{'value': 999}]}]})
        raise AssertionError(f'unexpected GET {url}')

    monkeypatch.setattr(ins.requests, 'get', fake_get)

    items = ins.get_instagram_media_insights('tok', 'IGID', limit=25, top_n=2)

    # ranked by likes+comments desc, capped to top_n=2
    assert [it['head'] for it in items] == ['high', 'mid']
    # reach fetched only for the 2 shown (not all 3)
    assert reach_calls == ['m_high', 'm_mid']
    assert items[0]['reach'] == 999


def test_media_reach_missing_permission_degrades_to_none(monkeypatch):
    media = [{'id': 'm1', 'caption': 'x', 'media_type': 'IMAGE', 'like_count': 3, 'comments_count': 0}]

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'data': media})
        raise Exception('(#10) requires instagram_manage_insights')

    monkeypatch.setattr(ins.requests, 'get', fake_get)

    items = ins.get_instagram_media_insights('tok', 'IGID', limit=25, top_n=5)

    assert items[0]['reach'] is None  # still returns the item, just no reach


def test_build_report_escapes_html_and_ranks():
    ig_items = [
        {'head': 'Benfica <b>2</b> & Porto', 'media_type': 'IMAGE', 'likes': 10, 'comments': 2, 'reach': 500},
        {'head': 'no caption post', 'media_type': 'REELS', 'likes': 4, 'comments': 0, 'reach': None},
    ]
    fb_stats = {'page_impressions_unique': 1234, 'page_post_engagements': 56}

    report = ins.build_insights_report(ig_items, fb_stats)

    assert 'Facebook' in report and 'охват: 1234' in report
    # caption HTML is escaped so Telegram HTML parse_mode won't break
    assert '&lt;b&gt;2&lt;/b&gt; &amp; Porto' in report
    assert '<b>2</b>' not in report
    # missing reach rendered as a dash
    assert '👁 — ·' in report


def test_build_report_when_no_data():
    report = ins.build_insights_report([], {})
    assert 'данные недоступны' in report


def test_build_report_includes_source_ranking():
    ranking = [('abola.pt', 812.4, 9), ('bbc.com', 120.0, 3)]
    report = ins.build_insights_report([], {}, source_ranking=ranking)
    assert 'Источники по охвату' in report
    assert '1. abola.pt — 812 (n=9)' in report
    assert '2. bbc.com — 120 (n=3)' in report


def test_build_report_includes_hour_ranking():
    hour_ranking = [('8', 900.0, 5), ('20', 300.0, 4)]
    report = ins.build_insights_report([], {}, hour_ranking=hour_ranking)
    assert 'Лучшие часы по охвату' in report
    assert '1. 08:00 — 900 (n=5)' in report
    assert '2. 20:00 — 300 (n=4)' in report


def test_parse_media_timestamp():
    assert ins._parse_media_timestamp('2026-06-12T21:00:00+0000') is not None
    assert ins._parse_media_timestamp('garbage') is None
    assert ins._parse_media_timestamp(None) is None


def test_get_instagram_metrics_by_head_returns_full_metrics(monkeypatch):
    now = ins._parse_media_timestamp('2026-06-13T00:00:00+0000')
    media = [
        {'id': 'old', 'caption': 'matured post', 'timestamp': '2026-06-01T00:00:00+0000',
         'like_count': 12, 'comments_count': 3},
        {'id': 'fresh', 'caption': 'fresh post', 'timestamp': '2026-06-12T23:00:00+0000',
         'like_count': 1, 'comments_count': 0},  # too fresh -> excluded
    ]

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'data': media})
        if url.endswith('/insights'):
            return _FakeResponse({'data': [{'name': 'reach', 'values': [{'value': 444}]}]})
        raise AssertionError(url)

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    result = ins.get_instagram_metrics_by_head('tok', 'IGID', limit=25, min_age_seconds=24 * 3600, now=now)

    assert result == {ins.make_head('matured post'): {'reach': 444, 'likes': 12, 'comments': 3}}


def test_get_facebook_post_insights_reads_object_fields_only(monkeypatch):
    # FB post reach metrics are deprecated in v18, so we no longer hit /insights —
    # only the object-fields engagement fetch (shares/comments/reactions).
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append(url)
        assert not url.endswith('/insights'), 'must not request deprecated post reach metric'
        return _FakeResponse({
            'shares': {'count': 4},
            'comments': {'summary': {'total_count': 7}},
            'reactions': {'summary': {'total_count': 20}},
        })

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    metrics = ins.get_facebook_post_insights('tok', 'PAGE_POST_1')
    assert metrics == {'shares': 4, 'comments': 7, 'likes': 20}
    assert len(calls) == 1  # single object fetch, no extra reach call


def test_get_facebook_post_insights_drops_shares_for_bare_media_id(monkeypatch):
    # A bare numeric id (no '_') is a media object (video from /videos returns only
    # 'id'); Video/Photo nodes have no 'shares' field, so requesting it 400s the
    # whole call. We must omit shares for those, still read comments/reactions, and
    # default shares to 0 — instead of losing all engagement signal.
    captured = {}

    def fake_get(url, params=None, **kwargs):
        captured['fields'] = params['fields']
        return _FakeResponse({
            'comments': {'summary': {'total_count': 3}},
            'reactions': {'summary': {'total_count': 9}},
        })

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    metrics = ins.get_facebook_post_insights('tok', '2412914399204739')

    assert 'shares' not in captured['fields']          # no invalid field => no 400
    assert metrics == {'shares': 0, 'comments': 3, 'likes': 9}


def test_get_facebook_post_insights_redacts_token_in_warning(monkeypatch):
    # requests stringifies the failing URL (with access_token) into the exception;
    # the warning must scrub it so the live token never lands in CI logs/artifacts.
    logged = []

    def fake_get(url, params=None, **kwargs):
        raise Exception(
            '400 Client Error: Bad Request for url: '
            'https://graph.facebook.com/v18.0/123_456?fields=shares&access_token=SECRETTOKEN')

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    monkeypatch.setattr(ins.logger, 'warning', lambda m: logged.append(m))

    ins.get_facebook_post_insights('tok', '123_456')

    assert logged, 'expected a warning to be logged'
    assert 'SECRETTOKEN' not in logged[0]
    assert 'access_token=***' in logged[0]


def test_get_facebook_post_insights_fail_open_on_missing_scope(monkeypatch):
    def fake_get(url, params=None, **kwargs):
        raise Exception('(#10) requires read_insights')

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    assert ins.get_facebook_post_insights('tok', 'PAGE_POST_1') == {}  # no crash, empty


def test_get_facebook_metrics_by_head_only_matured_with_id(monkeypatch):
    now = 100 * 24 * 3600
    pending = [
        {'head': 'h1', 'fb_id': 'P1', 'ts': now - 2 * 24 * 3600},   # matured + id -> fetched
        {'head': 'h2', 'fb_id': None, 'ts': now - 2 * 24 * 3600},   # no id -> skipped
        {'head': 'h3', 'fb_id': 'P3', 'ts': now - 3600},            # too fresh -> skipped
    ]
    monkeypatch.setattr(ins, 'get_facebook_post_insights',
                        lambda tok, pid: {'reach': 100, 'shares': 1})

    result = ins.get_facebook_metrics_by_head('tok', pending, now, min_age_seconds=24 * 3600)
    assert result == {'h1': {'reach': 100, 'shares': 1}}


def test_build_report_includes_dow_hour_ranking():
    report = ins.build_insights_report(
        [], {}, dow_hour_ranking=[('2-14', 900.0, 5), ('5-20', 300.0, 4)])
    assert 'Лучшие слоты день×час' in report
    assert '1. Ср 14:00 — 900 (n=5)' in report   # weekday 2 == Ср (Wed)
    assert '2. Сб 20:00 — 300 (n=4)' in report   # weekday 5 == Сб (Sat)


def test_fmt_dow_hour_tolerates_bad_key():
    assert ins._fmt_dow_hour('garbage') == 'garbage'


def test_build_report_includes_format_and_variant_rankings():
    report = ins.build_insights_report(
        [], {}, format_ranking=[('video', 80.0, 4), ('photo', 30.0, 6)],
        variant_ranking=[('tags:1-3', 70.0, 5)])
    assert 'Форматы по reward' in report and 'video: 80 (n=4)' in report
    assert 'Хэштеги по reward' in report and 'tags:1-3: 70 (n=5)' in report


def test_reach_by_head_skips_fresh_and_captionless(monkeypatch):
    now = ins._parse_media_timestamp('2026-06-13T00:00:00+0000')
    media = [
        {'id': 'old', 'caption': 'matured post', 'timestamp': '2026-06-01T00:00:00+0000'},   # 12d -> matured
        {'id': 'fresh', 'caption': 'fresh post', 'timestamp': '2026-06-12T23:00:00+0000'},   # 1h -> too fresh
        {'id': 'nocap', 'caption': '', 'timestamp': '2026-06-01T00:00:00+0000'},             # no caption
    ]

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'data': media})
        if url.endswith('/insights'):
            return _FakeResponse({'data': [{'name': 'reach', 'values': [{'value': 333}]}]})
        raise AssertionError(url)

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    result = ins.get_instagram_reach_by_head('tok', 'IGID', limit=25, min_age_seconds=24 * 3600, now=now)

    assert result == {ins.make_head('matured post'): 333}
