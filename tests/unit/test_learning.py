import os

from src.processor import learning


HOUR = 3600
DAY = 24 * HOUR


def test_load_state_missing_file_returns_fresh(tmp_path):
    state = learning.load_state(str(tmp_path / 'nope.json'))
    assert state == {'version': 1, 'pending': [], 'sources': {}, 'hours': {}}


def test_load_state_corrupt_file_returns_fresh(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text('{ not valid json')
    state = learning.load_state(str(path))
    assert state['pending'] == [] and state['sources'] == {}


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / 'sub' / 'state.json')  # nested dir must be created
    state = {'version': 1, 'pending': [{'head': 'h', 'source': 's', 'ts': 1}],
             'sources': {'s': {'reach_avg': 10.0, 'n': 2}}, 'hours': {'8': {'reach_avg': 10.0, 'n': 2}}}
    learning.save_state(path, state)
    assert os.path.exists(path)
    assert learning.load_state(path) == state


def test_record_publish_appends_and_skips_blanks():
    state = {'pending': [], 'sources': {}}
    learning.record_publish(state, 'head1', 'abola.pt', 1000)
    learning.record_publish(state, '', 'abola.pt', 1000)   # no head -> skipped
    learning.record_publish(state, 'head2', '', 1000)      # no source -> skipped
    assert state['pending'] == [{'head': 'head1', 'source': 'abola.pt', 'ts': 1000}]


def test_update_scores_attributes_matured_reach_and_prunes():
    now = 100 * DAY
    state = {
        'pending': [
            {'head': 'matured_matched', 'source': 'abola.pt', 'ts': now - 2 * DAY},
            {'head': 'too_fresh', 'source': 'bbc.com', 'ts': now - 1 * HOUR},
            {'head': 'matured_unmatched_old', 'source': 'rtp.pt', 'ts': now - 30 * DAY},
        ],
        'sources': {},
    }
    reach_by_head = {'matured_matched': 500}

    learning.update_scores(state, reach_by_head, now,
                           maturation_seconds=DAY, max_age_seconds=7 * DAY, alpha=0.3)

    # matured + matched => scored, removed from pending
    assert state['sources']['abola.pt'] == {'reach_avg': 500.0, 'n': 1}
    heads_left = {p['head'] for p in state['pending']}
    assert 'matured_matched' not in heads_left
    assert 'too_fresh' in heads_left              # not matured yet -> kept
    assert 'matured_unmatched_old' not in heads_left  # past max_age, unmatched -> pruned


def test_update_scores_ew_average_on_repeat():
    now = 100 * DAY
    state = {
        'pending': [{'head': 'h', 'source': 'abola.pt', 'ts': now - 2 * DAY}],
        'sources': {'abola.pt': {'reach_avg': 100.0, 'n': 3}},
    }
    learning.update_scores(state, {'h': 200}, now, DAY, 7 * DAY, alpha=0.5)
    # 0.5*200 + 0.5*100 = 150
    assert state['sources']['abola.pt'] == {'reach_avg': 150.0, 'n': 4}


def test_order_sources_scored_desc_unscored_first():
    sources = {
        'low': {'reach_avg': 10.0, 'n': 5},
        'high': {'reach_avg': 900.0, 'n': 5},
        'mid': {'reach_avg': 100.0, 'n': 1},
    }
    names = ['low', 'high', 'unseen', 'mid']
    ordered = learning.order_sources(names, sources, default_prior=float('inf'))
    # unseen (prior inf) first, then high, mid, low
    assert ordered == ['unseen', 'high', 'mid', 'low']


def test_order_sources_exploit_when_prior_low():
    sources = {'high': {'reach_avg': 900.0, 'n': 5}}
    ordered = learning.order_sources(['high', 'unseen'], sources, default_prior=0.0)
    assert ordered == ['high', 'unseen']  # scored beats zero-prior unscored


def test_update_scores_attributes_to_publish_hour():
    # Matured reach also lands in state['hours'] keyed by the post's publish hour.
    publish_ts = 1_700_000_000
    expected_hour = str(learning._hour_of(publish_ts))
    state = {'pending': [{'head': 'h', 'source': 'abola.pt', 'ts': publish_ts}], 'sources': {}, 'hours': {}}
    learning.update_scores(state, {'h': 400}, publish_ts + 2 * DAY, DAY, 7 * DAY, alpha=0.3)

    assert state['hours'] == {expected_hour: {'reach_avg': 400.0, 'n': 1}}
    assert state['sources']['abola.pt'] == {'reach_avg': 400.0, 'n': 1}


def test_hour_budget_tiers_by_reach():
    hours = {
        '8':  {'reach_avg': 900.0, 'n': 5},   # top
        '10': {'reach_avg': 500.0, 'n': 5},   # mid
        '12': {'reach_avg': 100.0, 'n': 5},   # bottom
    }
    assert learning.hour_budget(hours, 8, base_cap=3, min_samples=3) == 3   # top -> full
    assert learning.hour_budget(hours, 10, base_cap=3, min_samples=3) == 2  # mid -> ~half
    assert learning.hour_budget(hours, 12, base_cap=3, min_samples=3) == 1  # bottom -> 1, never 0


def test_hour_budget_full_when_insufficient_or_unseen_data():
    hours = {'8': {'reach_avg': 900.0, 'n': 5}, '10': {'reach_avg': 100.0, 'n': 5}}
    # < 3 well-sampled hours -> explore at full cap
    assert learning.hour_budget(hours, 8, base_cap=3, min_samples=3) == 3
    # current hour under-sampled -> full cap (keep sampling it)
    hours3 = dict(hours, **{'12': {'reach_avg': 500.0, 'n': 5}, '14': {'reach_avg': 50.0, 'n': 1}})
    assert learning.hour_budget(hours3, 14, base_cap=3, min_samples=3) == 3


def test_top_sources_only_scored_sorted_desc():
    sources = {
        'a': {'reach_avg': 50.0, 'n': 2},
        'b': {'reach_avg': 500.0, 'n': 1},
        'c': {'reach_avg': 0.0, 'n': 0},  # never scored -> excluded
    }
    assert learning.top_sources(sources) == [('b', 500.0, 1), ('a', 50.0, 2)]
