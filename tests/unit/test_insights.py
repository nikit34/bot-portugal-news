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
