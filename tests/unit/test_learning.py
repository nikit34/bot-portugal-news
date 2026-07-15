import os

from src.processor import learning


HOUR = 3600
DAY = 24 * HOUR


def test_load_state_missing_file_returns_fresh(tmp_path):
    state = learning.load_state(str(tmp_path / 'nope.json'))
    assert state == {'version': 1, 'pending': [], 'sources': {}, 'hours': {},
                     'ig_quota': {'day': '', 'posts': 0}}


def test_load_state_corrupt_file_returns_fresh(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text('{ not valid json')
    state = learning.load_state(str(path))
    assert state['pending'] == [] and state['sources'] == {}


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / 'sub' / 'state.json')  # nested dir must be created
    state = {'version': 1, 'pending': [{'head': 'h', 'source': 's', 'ts': 1}],
             'sources': {'s': {'reach_avg': 10.0, 'n': 2}}, 'hours': {'8': {'reach_avg': 10.0, 'n': 2}},
             'ig_quota': {'day': '2026-06-13', 'posts': 4}}
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
    # the unmatched post must NOT steal the matched post's reach (regression: a loose
    # fuzzy match used to credit rtp.pt here silently)
    assert 'rtp.pt' not in state['sources']
    heads_left = {p['head'] for p in state['pending']}
    assert 'matured_matched' not in heads_left
    assert 'too_fresh' in heads_left              # not matured yet -> kept
    assert 'matured_unmatched_old' not in heads_left  # past max_age, unmatched -> pruned


def test_reach_not_attributed_to_similar_but_distinct_head():
    # Two distinct templated headlines share boilerplate (high fuzzy similarity) but
    # neither is a prefix of the other => no cross-attribution.
    now = 100 * DAY
    state = {'pending': [{'head': 'Benfica vence o Sporting por 2-1 na Luz', 'source': 'rtp.pt',
                          'ts': now - 2 * DAY}], 'sources': {}, 'hours': {}}
    reach_by_head = {'Benfica vence o Porto por 3-0 na Luz': 900}

    learning.update_scores(state, reach_by_head, now, DAY, 7 * DAY, alpha=0.3)

    assert state['sources'] == {}  # not a prefix => not attributed


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


def test_update_scores_fuzzy_match_when_head_shifted():
    # Item 8: reach key differs from the publish head (hashtags shifted the read-back
    # head) but is_similar => still attributed.
    now = 100 * DAY
    state = {'pending': [{'head': 'Benfica vence o Porto na Luz', 'source': 'abola.pt', 'ts': now - 2 * DAY}],
             'sources': {}, 'hours': {}}
    reach_by_head = {'Benfica vence o Porto na Luz #benfica #porto': 700}

    learning.update_scores(state, reach_by_head, now, DAY, 7 * DAY, alpha=0.3)

    assert state['sources']['abola.pt'] == {'reach_avg': 700.0, 'n': 1}
    assert state['pending'] == []  # attributed and dropped


def test_ig_quota_today_and_add():
    state = {'ig_quota': {'day': '2026-06-13', 'posts': 5}}
    assert learning.ig_posts_today(state, '2026-06-13') == 5
    assert learning.ig_posts_today(state, '2026-06-14') == 0  # different day -> 0

    learning.add_ig_posts(state, '2026-06-13', 2)
    assert state['ig_quota'] == {'day': '2026-06-13', 'posts': 7}

    learning.add_ig_posts(state, '2026-06-14', 1)  # new day resets the counter
    assert state['ig_quota'] == {'day': '2026-06-14', 'posts': 1}


def test_top_sources_only_scored_sorted_desc():
    sources = {
        'a': {'reach_avg': 50.0, 'n': 2},
        'b': {'reach_avg': 500.0, 'n': 1},
        'c': {'reach_avg': 0.0, 'n': 0},  # never scored -> excluded
    }
    assert learning.top_sources(sources) == [('b', 500.0, 1), ('a', 50.0, 2)]


# --- post-id / feature persistence ------------------------------------------

def test_record_publish_stores_features_when_present():
    state = {'pending': []}
    learning.record_publish(state, 'h', 'abola.pt', 1000,
                            fb_id='PAGE_1', ig_id='IG_1', is_video=True, hashtag_n=3)
    assert state['pending'] == [{'head': 'h', 'source': 'abola.pt', 'ts': 1000,
                                 'fb_id': 'PAGE_1', 'ig_id': 'IG_1', 'is_video': True, 'hashtag_n': 3}]


def test_record_publish_omits_none_features():
    # Backward-compat: no features -> the minimal legacy shape (no None keys).
    state = {'pending': []}
    learning.record_publish(state, 'h', 'abola.pt', 1000, fb_id=None, ig_id=None)
    assert state['pending'] == [{'head': 'h', 'source': 'abola.pt', 'ts': 1000}]


# --- engagement-weighted reward ---------------------------------------------

def test_reward_for_weights_meaningful_interactions_above_reach():
    weights = {'share': 3.0, 'comment': 2.0, 'like': 1.0, 'reach': 0.05}
    reward = learning.reward_for({'shares': 1, 'comments': 2, 'likes': 10, 'reach': 1000}, weights)
    assert reward == 3 * 1 + 2 * 2 + 1 * 10 + 0.05 * 1000  # 67.0


def test_reward_for_tolerates_missing_metrics():
    assert learning.reward_for({'reach': 200}, {'reach': 0.5}) == 100.0


def test_reward_for_rewards_saves_and_watch_ignores_likes():
    # 2026 scheme: shares/saves/watch carry the reward, likes are zero-weighted.
    weights = {'share': 4.0, 'save': 3.0, 'comment': 2.0, 'watch': 0.3, 'like': 0.0, 'reach': 0.05}
    m = {'shares': 2, 'saves': 5, 'comments': 1, 'watch': 10.0, 'likes': 100, 'reach': 1000}
    # 4*2 + 3*5 + 2*1 + 0.3*10 + 0*100 + 0.05*1000
    assert learning.reward_for(m, weights) == 8 + 15 + 2 + 3 + 0 + 50  # 78.0


def test_update_scores_metrics_attributes_reward_and_format():
    now = 100 * DAY
    weights = {'share': 3.0, 'comment': 2.0, 'like': 1.0, 'reach': 0.05}
    state = {'pending': [{'head': 'h', 'source': 'abola.pt', 'ts': now - 2 * DAY, 'is_video': True}],
             'sources': {}, 'hours': {}}
    metrics = {'h': {'shares': 1, 'comments': 2, 'likes': 10, 'reach': 1000}}

    learning.update_scores_metrics(state, metrics, weights, now, DAY, 7 * DAY, alpha=0.3)

    assert state['sources']['abola.pt'] == {'reach_avg': 67.0, 'n': 1}
    assert state['formats']['video'] == {'reach_avg': 67.0, 'n': 1}
    assert state['pending'] == []


def test_update_scores_metrics_logs_variants_when_enabled():
    now = 100 * DAY
    weights = {'reach': 1.0}
    state = {'pending': [{'head': 'h', 'source': 's', 'ts': now - 2 * DAY,
                          'is_video': False, 'hashtag_n': 2}], 'sources': {}, 'hours': {}}
    learning.update_scores_metrics(state, {'h': {'reach': 50}}, weights, now, DAY, 7 * DAY,
                                   alpha=0.3, log_variants=True)
    assert state['variants']['tags:1-3'] == {'reach_avg': 50.0, 'n': 1}
    assert state['formats']['photo'] == {'reach_avg': 50.0, 'n': 1}


# --- Phase 1: reward-proportional amplification -----------------------------

def _amp_state(reach_avg, n):
    now = 100 * DAY
    return now, {'pending': [{'head': 'h', 'source': 's', 'ts': now - 2 * DAY}],
                 'sources': {'s': {'reach_avg': reach_avg, 'n': n}}, 'hours': {}}


def test_amp_disabled_is_fixed_alpha_ew():
    now, state = _amp_state(100.0, 3)
    learning.update_scores_metrics(state, {'h': {'reach': 200}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.5, amp_enabled=False)
    assert state['sources']['s'] == {'reach_avg': 150.0, 'n': 4}  # 0.5*200 + 0.5*100


def test_amp_big_winner_takes_larger_step():
    now, state = _amp_state(100.0, 3)
    # excess/ref = 100/100 = 1 => alpha_eff = min(0.6, 0.3*(1+1)) = 0.6
    learning.update_scores_metrics(state, {'h': {'reach': 200}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, amp_enabled=True, amp_gain=1.0, amp_alpha_max=0.6)
    # 0.6*200 + 0.4*100 = 160, larger than fixed-alpha's 0.3 -> 130
    assert state['sources']['s'] == {'reach_avg': 160.0, 'n': 4}


def test_amp_alpha_max_caps_runaway():
    now, state = _amp_state(10.0, 3)
    learning.update_scores_metrics(state, {'h': {'reach': 10000}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, amp_enabled=True, amp_gain=1.0, amp_alpha_max=0.6)
    # step clamps to alpha_max=0.6: 0.6*10000 + 0.4*10 = 6004.0
    assert state['sources']['s'] == {'reach_avg': 6004.0, 'n': 4}


def test_amp_first_sample_ignores_gain():
    now = 100 * DAY
    state = {'pending': [{'head': 'h', 'source': 's', 'ts': now - 2 * DAY}], 'sources': {}, 'hours': {}}
    learning.update_scores_metrics(state, {'h': {'reach': 500}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, amp_enabled=True, amp_gain=5.0, amp_alpha_max=0.9)
    # empty bucket => seeded reach_avg=reward, n=1 regardless of amp
    assert state['sources']['s'] == {'reach_avg': 500.0, 'n': 1}


def test_amp_flop_moves_by_base_alpha():
    now, state = _amp_state(100.0, 3)
    # reward below the bucket mean => excess 0 => effective alpha == base alpha
    learning.update_scores_metrics(state, {'h': {'reach': 40}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, amp_enabled=True, amp_gain=1.0, amp_alpha_max=0.6)
    # 0.3*40 + 0.7*100 = 82.0 (same as fixed alpha)
    assert state['sources']['s'] == {'reach_avg': 82.0, 'n': 4}


def test_amp_n_counts_one_per_event():
    now, state = _amp_state(100.0, 4)
    learning.update_scores_metrics(state, {'h': {'reach': 300}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, amp_enabled=True, amp_gain=2.0, amp_alpha_max=0.8)
    assert state['sources']['s']['n'] == 5  # one increment per event, UCB math preserved


# --- Phase 2: percentile winner capture -------------------------------------

def test_percentile_helper():
    assert learning._percentile([], 90) is None
    assert learning._percentile([42.0], 90) == 42.0
    assert learning._percentile([0.0, 10.0], 50) == 5.0


def _winner_state(head, reward_samples, is_followup=False):
    now = 100 * DAY
    post = {'head': head, 'source': 's', 'ts': now - 2 * DAY}
    if is_followup:
        post['is_followup'] = True
    return now, {'pending': [post], 'sources': {}, 'hours': {},
                 'reward_samples': list(reward_samples)}


def test_winner_capture_inert_when_pct_none():
    now = 100 * DAY
    state = {'pending': [{'head': 'h', 'source': 's', 'ts': now - 2 * DAY}], 'sources': {}, 'hours': {}}
    learning.update_scores_metrics(state, {'h': {'reach': 500}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, winner_pct=None)
    assert 'recent_winners' not in state and 'reward_samples' not in state


def test_winner_capture_collects_samples_below_min():
    now, state = _winner_state('h', [10.0, 20.0])
    learning.update_scores_metrics(state, {'h': {'reach': 999}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, winner_pct=90, winner_min_samples=10)
    assert state.get('recent_winners', []) == []   # threshold not built yet (too few samples)
    assert state['reward_samples'][-1] == 999.0     # but the sample is recorded


def test_winner_capture_above_percentile():
    now, state = _winner_state('win', [float(i) for i in range(10)])  # 0..9, p90 ~ 8.1
    learning.update_scores_metrics(state, {'win': {'reach': 50}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, winner_pct=90, winner_min_samples=10)
    assert state['recent_winners'] == [{'head': 'win', 'source': 's', 'reward': 50.0, 'ts': now}]


def test_winner_capture_below_percentile_not_recorded():
    now, state = _winner_state('meh', [float(i) for i in range(10, 110)])  # p90 ~ 99
    learning.update_scores_metrics(state, {'meh': {'reach': 20}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, winner_pct=90, winner_min_samples=10)
    assert state.get('recent_winners', []) == []


def test_winner_capture_ignores_zero_reward():
    # zero-heavy distribution => p90 is 0, but a no-engagement post is never a winner
    now, state = _winner_state('z', [0.0] * 20)
    learning.update_scores_metrics(state, {'z': {'reach': 0}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, winner_pct=90, winner_min_samples=10)
    assert state.get('recent_winners', []) == []


def test_winner_capture_excludes_followups():
    now, state = _winner_state('fu', [float(i) for i in range(10)], is_followup=True)
    learning.update_scores_metrics(state, {'fu': {'reach': 999}}, {'reach': 1.0}, now, DAY, 7 * DAY,
                                   alpha=0.3, winner_pct=90, winner_min_samples=10)
    assert state.get('recent_winners', []) == []    # depth guard
    assert state['reward_samples'][-1] == 999.0      # still sampled


def test_winner_and_sample_lists_bounded():
    now = 100 * DAY
    state = {'pending': [{'head': f'h{i}', 'source': 's', 'ts': now - 2 * DAY} for i in range(5)],
             'sources': {}, 'hours': {},
             'reward_samples': [100.0] * 10, 'recent_winners': [{'x': 1}] * 3}
    metrics = {f'h{i}': {'reach': 1000} for i in range(5)}
    learning.update_scores_metrics(state, metrics, {'reach': 1.0}, now, DAY, 7 * DAY, alpha=0.3,
                                   winner_pct=50, winner_min_samples=1, winners_max=4, samples_max=8)
    assert len(state['recent_winners']) == 4   # 3 old + 5 new, truncated to most-recent 4
    assert len(state['reward_samples']) == 8   # 10 old + 5 new, truncated to most-recent 8


# --- Phase 3: fresh-winner counting -----------------------------------------

def test_count_fresh_winners_within_window():
    now = 1000.0
    state = {'recent_winners': [
        {'head': 'a', 'source': 's', 'reward': 5, 'ts': now - 100},    # fresh
        {'head': 'b', 'source': 's', 'reward': 5, 'ts': now - 5000},   # stale
    ]}
    assert learning.count_fresh_winners(state, now, within_seconds=1000) == 1
    assert learning.count_fresh_winners({}, now, 1000) == 0


# --- UCB source ordering + sample gate --------------------------------------

def test_order_sources_ucb_prefers_under_sampled_on_tie():
    sources = {'a': {'reach_avg': 100.0, 'n': 10}, 'b': {'reach_avg': 100.0, 'n': 1}}
    # equal reward, b sampled far less -> exploration bonus lifts b above a
    assert learning.order_sources(['a', 'b'], sources, 0.0, ucb_c=1.0) == ['b', 'a']
    # c=0 reproduces the greedy avg-sort exactly (stable -> input order on ties)
    assert learning.order_sources(['a', 'b'], sources, 0.0, ucb_c=0.0) == ['a', 'b']


def test_well_sampled_sources_counts_above_threshold():
    sources = {'a': {'reach_avg': 1, 'n': 3}, 'b': {'reach_avg': 1, 'n': 2}, 'c': {'reach_avg': 1, 'n': 5}}
    assert learning.well_sampled_sources(sources, min_samples=3) == 2


# --- dow-hour buckets (day-of-week × hour) ----------------------------------

def test_dow_hour_key_format():
    # 1700000000 == 2023-11-14 22:13:20 UTC -> Tuesday(1) hour 22
    assert learning._dow_hour_of(1_700_000_000) == '1-22'


def test_update_scores_also_fills_dow_hours():
    publish_ts = 1_700_000_000
    state = {'pending': [{'head': 'h', 'source': 's', 'ts': publish_ts}],
             'sources': {}, 'hours': {}}
    learning.update_scores(state, {'h': 400}, publish_ts + 2 * DAY, DAY, 7 * DAY, alpha=0.3)
    # both the coarse hour bucket and the fine dow-hour bucket are filled
    assert state['hours'] == {str(learning._hour_of(publish_ts)): {'reach_avg': 400.0, 'n': 1}}
    assert state['dow_hours'] == {learning._dow_hour_of(publish_ts): {'reach_avg': 400.0, 'n': 1}}


def test_hour_budget_prefers_well_sampled_dow_hour():
    # Tuesday(2) 14:00 is top-tier among dow-hour peers -> full cap, even though the
    # coarse hour bucket alone would have too few entries to tier.
    hours = {'14': {'reach_avg': 100.0, 'n': 5}}
    dow = {'2-14': {'reach_avg': 900.0, 'n': 5},
           '2-10': {'reach_avg': 500.0, 'n': 5},
           '2-8': {'reach_avg': 100.0, 'n': 5}}
    assert learning.hour_budget(hours, 14, 3, 3, dow_hours=dow, current_dow=2) == 3


def test_hour_budget_falls_back_to_hour_when_dow_thin():
    # Current dow-hour cell is under-sampled (n<3) -> partial pooling backs off to
    # the coarse hour-only tiering (hour 12 is bottom tier -> 1).
    hours = {'8': {'reach_avg': 900.0, 'n': 5},
             '10': {'reach_avg': 500.0, 'n': 5},
             '12': {'reach_avg': 100.0, 'n': 5}}
    dow = {'2-12': {'reach_avg': 900.0, 'n': 1}}
    assert learning.hour_budget(hours, 12, 3, 3, dow_hours=dow, current_dow=2) == 1


def test_hour_budget_backward_compatible_without_dow():
    # No dow args => identical to the old hour-only behavior.
    hours = {'8': {'reach_avg': 900.0, 'n': 5}, '10': {'reach_avg': 500.0, 'n': 5},
             '12': {'reach_avg': 100.0, 'n': 5}}
    assert learning.hour_budget(hours, 8, 3, 3) == 3
    assert learning.hour_budget(hours, 12, 3, 3) == 1
