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
    fb_stats = {'page_reach': 1234, 'page_post_engagements': 56}

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
    assert 'Источники по reward' in report
    assert '1. abola.pt — 812 (n=9)' in report
    assert '2. bbc.com — 120 (n=3)' in report


def test_build_report_includes_hour_ranking():
    hour_ranking = [('8', 900.0, 5), ('20', 300.0, 4)]
    report = ins.build_insights_report([], {}, hour_ranking=hour_ranking)
    assert 'Лучшие часы по reward' in report
    assert '1. 08:00 — 900 (n=5)' in report
    assert '2. 20:00 — 300 (n=4)' in report


def test_parse_media_timestamp():
    assert ins._parse_media_timestamp('2026-06-12T21:00:00+0000') is not None
    assert ins._parse_media_timestamp('garbage') is None
    assert ins._parse_media_timestamp(None) is None


def test_get_instagram_metrics_by_head_returns_full_metrics(monkeypatch):
    now = ins._parse_media_timestamp('2026-06-13T00:00:00+0000')
    media = [
        {'id': 'old', 'caption': 'matured post', 'media_type': 'REELS',
         'timestamp': '2026-06-01T00:00:00+0000', 'like_count': 12, 'comments_count': 3},
        {'id': 'fresh', 'caption': 'fresh post', 'media_type': 'IMAGE',
         'timestamp': '2026-06-12T23:00:00+0000', 'like_count': 1, 'comments_count': 0},  # too fresh
    ]

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'data': media})
        if url.endswith('/insights'):
            metric = (params or {}).get('metric', '')
            data = []
            if 'reach' in metric:
                data.append({'name': 'reach', 'values': [{'value': 444}]})
            if 'saved' in metric:
                data.append({'name': 'saved', 'values': [{'value': 30}]})
            if 'shares' in metric:
                data.append({'name': 'shares', 'values': [{'value': 8}]})
            if 'ig_reels_avg_watch_time' in metric:
                data.append({'name': 'ig_reels_avg_watch_time', 'values': [{'value': 5200}]})  # ms
            return _FakeResponse({'data': data})
        raise AssertionError(url)

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    result = ins.get_instagram_metrics_by_head('tok', 'IGID', limit=25, min_age_seconds=24 * 3600, now=now)

    # reach/saved/shares from the combined call; watch (5200ms -> 5.2s) from the reels-only call
    assert result == {ins.make_head('matured post'): {
        'reach': 444, 'saves': 30, 'shares': 8, 'watch': 5.2, 'likes': 12, 'comments': 3}}


def test_get_instagram_metrics_degrades_when_shares_unsupported(monkeypatch):
    # On an older Graph version `shares` can 400 the whole insights call. We must keep
    # the reach anchor + saves and just drop shares, not lose the post.
    now = ins._parse_media_timestamp('2026-06-13T00:00:00+0000')
    media = [{'id': 'old', 'caption': 'post', 'media_type': 'IMAGE',
              'timestamp': '2026-06-01T00:00:00+0000', 'like_count': 2, 'comments_count': 1}]

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'data': media})
        if url.endswith('/insights'):
            metric = (params or {}).get('metric', '')
            if 'shares' in metric:                       # unsupported -> 400 the whole call
                raise Exception('(#100) shares is not a valid metric')
            data = []
            if 'reach' in metric:
                data.append({'name': 'reach', 'values': [{'value': 100}]})
            if 'saved' in metric:
                data.append({'name': 'saved', 'values': [{'value': 9}]})
            return _FakeResponse({'data': data})
        raise AssertionError(url)

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    result = ins.get_instagram_metrics_by_head('tok', 'IGID', limit=25, min_age_seconds=24 * 3600, now=now)

    head = ins.make_head('post')
    assert result[head]['reach'] == 100 and result[head]['saves'] == 9
    assert result[head]['shares'] is None          # dropped, but reach/saves survived
    assert result[head]['watch'] is None           # IMAGE -> no reels watch-time


def test_fetch_recent_media_fail_open_on_error(monkeypatch):
    # A broken/unlinked IG account (code 100/33) must NOT crash the run — the media
    # list fetch is best-effort and returns [] so scoring/history degrade gracefully.
    def boom(url, params=None, **kwargs):
        raise Exception("400 for url ...17841.../media?access_token=EAAsecrettoken does not exist")

    monkeypatch.setattr(ins.requests, 'get', boom)
    assert ins._fetch_recent_media('tok', '17841412428059741', 25) == []


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


def test_page_insights_prefers_new_reach_metric(monkeypatch):
    # page_impressions_unique died 15.06.2026 for ALL API versions. We must ask for
    # its replacement first and normalize the key to 'page_reach'.
    asked = []

    def fake_get(url, params=None, **kwargs):
        asked.append(params['metric'])
        return _FakeResponse({'data': [
            {'name': 'page_total_media_view_unique', 'values': [{'value': 777}]},
            {'name': 'page_post_engagements', 'values': [{'value': 42}]},
        ]})

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    stats = ins.get_facebook_page_insights('tok', 'PAGE')

    assert asked[0].startswith('page_total_media_view_unique')
    assert stats == {'page_reach': 777, 'page_post_engagements': 42}


def test_page_insights_falls_back_to_legacy_reach_metric(monkeypatch):
    # Where the new metric isn't served yet, the legacy one must still be tried —
    # otherwise the digest silently loses page reach entirely.
    asked = []

    def fake_get(url, params=None, **kwargs):
        metric = params['metric']
        asked.append(metric)
        if metric.startswith('page_total_media_view_unique'):
            raise Exception('(#100) page_total_media_view_unique is not valid')
        return _FakeResponse({'data': [{'name': 'page_impressions_unique',
                                        'values': [{'value': 55}]}]})

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    stats = ins.get_facebook_page_insights('tok', 'PAGE')

    assert len(asked) == 2
    assert stats == {'page_reach': 55}


@pytest.fixture(autouse=True)
def _reset_earnings_circuit():
    ins._earnings_unavailable = False


def test_post_earnings_stops_asking_after_first_miss(monkeypatch):
    # На не-монетизированной странице метрика недоступна для ВСЕХ постов. Без
    # предохранителя каждый скоринг слал бы по два заведомо провальных запроса
    # на каждый зрелый пост.
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append(params['metric'])
        raise Exception('(#100) not a valid metric')

    monkeypatch.setattr(ins.requests, 'get', fake_get)

    assert ins.get_facebook_post_earnings('tok', 'P1') is None
    assert len(calls) == 2                     # content_monetization + approximate
    assert ins.get_facebook_post_earnings('tok', 'P2') is None
    assert len(calls) == 2                     # второй пост уже не спрашиваем


def test_post_earnings_falls_back_to_approximate(monkeypatch):
    # content_monetization_earnings exists only from Graph v23 and only for pages
    # onboarded to Content Monetization; monetization_approximate_earnings is the
    # backstop. Neither available => None (money term contributes nothing).
    def fake_get(url, params=None, **kwargs):
        if params['metric'] == 'content_monetization_earnings':
            raise Exception('(#100) not a valid metric')
        return _FakeResponse({'data': [{'name': 'monetization_approximate_earnings',
                                        'values': [{'value': 1.25}]}]})

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    assert ins.get_facebook_post_earnings('tok', 'P1') == 1.25


def test_post_earnings_none_when_not_monetized(monkeypatch):
    monkeypatch.setattr(ins.requests, 'get',
                        lambda *a, **k: (_ for _ in ()).throw(Exception('(#10) no permission')))
    assert ins.get_facebook_post_earnings('tok', 'P1') is None


def test_video_watch_minutes_converts_from_milliseconds(monkeypatch):
    def fake_get(url, params=None, **kwargs):
        assert url.endswith('/video_insights')
        assert params['metric'] == 'total_video_view_total_time'
        return _FakeResponse({'data': [{'name': 'total_video_view_total_time',
                                        'values': [{'value': 180000}]}]})   # 3 min in ms

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    assert ins.get_facebook_video_watch_minutes('tok', 'VID') == 3.0


def test_metrics_by_head_adds_money_terms_for_video_only(monkeypatch):
    now = 100 * 24 * 3600
    pending = [
        {'head': 'vid', 'fb_id': 'V1', 'fb_media_id': 'V1', 'ts': now - 2 * 24 * 3600,
         'is_video': True},
        {'head': 'pic', 'fb_id': 'P_1', 'ts': now - 2 * 24 * 3600, 'is_video': False},
    ]
    monkeypatch.setattr(ins, 'get_facebook_post_insights', lambda tok, pid: {'shares': 1})
    monkeypatch.setattr(ins, 'get_facebook_post_earnings', lambda tok, pid: 0.02)
    watch_calls = []
    monkeypatch.setattr(ins, 'get_facebook_video_watch_minutes',
                        lambda tok, vid: watch_calls.append(vid) or 12.5)

    result = ins.get_facebook_metrics_by_head(
        'tok', pending, now, 24 * 3600, with_earnings=True, with_watch_time=True)

    # watch time only queried for the video (photos have no /video_insights node)
    assert watch_calls == ['V1']
    assert result['vid'] == {'shares': 1, 'earnings': 0.02, 'watch_total': 12.5}
    assert result['pic'] == {'shares': 1, 'earnings': 0.02}


def test_metrics_by_head_without_money_flags_is_unchanged(monkeypatch):
    now = 100 * 24 * 3600
    pending = [{'head': 'h1', 'fb_id': 'P1', 'ts': now - 2 * 24 * 3600, 'is_video': True}]
    monkeypatch.setattr(ins, 'get_facebook_post_insights', lambda tok, pid: {'shares': 2})
    monkeypatch.setattr(ins, 'get_facebook_post_earnings',
                        lambda *a: pytest.fail('must not fetch earnings when disabled'))
    monkeypatch.setattr(ins, 'get_facebook_video_watch_minutes',
                        lambda *a: pytest.fail('must not fetch watch time when disabled'))

    assert ins.get_facebook_metrics_by_head('tok', pending, now, 24 * 3600) == {'h1': {'shares': 2}}


def test_page_monetization_sums_watch_time_across_days(monkeypatch):
    def fake_get(url, params=None, **kwargs):
        if params.get('fields'):
            return _FakeResponse({'followers_count': 1234})
        if params.get('metric') == 'page_video_view_time':
            return _FakeResponse({'data': [{'name': 'page_video_view_time', 'values': [
                {'value': 60000}, {'value': 120000}, {'value': 60000}]}]})   # 1+2+1 = 4 min
        return _FakeResponse({'data': []})

    monkeypatch.setattr(ins.requests, 'get', fake_get)
    result = ins.get_facebook_page_monetization('tok', 'PAGE')

    assert result['followers'] == 1234
    assert result['watch_minutes_60d'] == 4.0
    assert 'earnings_28d' not in result       # not monetized => key simply absent


def test_build_report_shows_distance_to_monetization():
    report = ins.build_insights_report([], {}, monetization={
        'followers': 500, 'watch_minutes_60d': 6000, 'watch_window_days': 60,
        'earnings_28d': 0.0})

    assert 'Допуск в монетизацию' in report
    assert '500/5000 подписчиков' in report          # reels track
    assert '500/10000 подписчиков' in report         # full track
    assert '6000/60000 мин за 60д' in report
    assert 'заработок за 28д: $0.00' in report


def test_build_report_omits_monetization_block_without_data():
    assert 'Допуск в монетизацию' not in ins.build_insights_report([], {}, monetization={})
    assert 'Допуск в монетизацию' not in ins.build_insights_report([], {})


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


def test_fmt_reward_keeps_small_values_visible():
    # Округление до целого прятало всю разницу между источниками: 0.199 и строгий
    # ноль печатались одинаково, хотя это след вовлечённости против её полного
    # отсутствия на десятках постов.
    assert ins._fmt_reward(0) == '0'
    assert ins._fmt_reward(0.19860) == '0.20'
    assert ins._fmt_reward(3.20591) == '3.21'
    assert ins._fmt_reward(0.00019) == '1.9e-04'    # пыль, но НЕ ноль
    # крупные значения (минуты просмотра дайджеста, старые reach-числа) — целыми
    assert ins._fmt_reward(812.4) == '812'
    assert ins._fmt_reward(80.0) == '80'


def test_source_ranking_distinguishes_zero_from_dust():
    report = ins.build_insights_report([], {}, source_ranking=[
        ('ge.globo.com', 0.00019, 61), ('rtp.pt/desporto', 0.0, 41)])
    assert 'ge.globo.com — 1.9e-04 (n=61)' in report
    assert 'rtp.pt/desporto — 0 (n=41)' in report
