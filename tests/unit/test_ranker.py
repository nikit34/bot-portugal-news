from src.processor.ranker import candidate_score, _length_bonus


def test_length_bonus_peaks_in_sweet_spot():
    assert _length_bonus('x' * 60) == 1.0          # in 40..90
    assert _length_bonus('x' * 20) < 1.0            # too short
    assert _length_bonus('x' * 200) < 1.0           # too long
    assert _length_bonus('') == 0.0


def test_learned_source_lifts_score():
    state = {'sources': {'good': {'reach_avg': 900.0, 'n': 5},
                         'bad': {'reach_avg': 100.0, 'n': 5}}, 'hours': {}}
    head = 'Benfica vence o Porto por 2-1 no classico da Luz hoje'  # in sweet spot
    good = candidate_score({'head': head, 'source': 'good', 'text': head}, state, current_hour=12)
    bad = candidate_score({'head': head, 'source': 'bad', 'text': head}, state, current_hour=12)
    assert good > bad


def test_clickbait_penalises_score():
    state = {'sources': {}, 'hours': {}}
    head = 'Benfica vence o Porto por 2-1 no classico da Luz hoje'
    clean = candidate_score({'head': head, 'source': 's', 'text': head}, state, 12)
    baity = candidate_score(
        {'head': head, 'source': 's', 'text': head + ' marque um amigo comente SIM'}, state, 12)
    assert baity < clean


def test_cold_start_falls_back_to_heuristics():
    # No learned data => score is purely heuristic (length - clickbait), no crash.
    state = {'sources': {}, 'hours': {}}
    score = candidate_score({'head': 'x' * 60, 'source': 'new', 'text': 'x' * 60}, state, 12)
    assert score == 1.0  # length bonus 1.0, no learned, no clickbait


def test_video_bonus_lifts_score():
    # A short-caption video must outscore an identical photo so it can win a best-K
    # slot instead of being crowded out by longer text posts.
    import src.processor.ranker as rk
    state = {'sources': {}, 'hours': {}}
    head = '\U0001F525 Golo!'  # tiny caption -> weak length bonus
    photo = candidate_score({'head': head, 'source': 's', 'text': head, 'is_video': False}, state, 12)
    video = candidate_score({'head': head, 'source': 's', 'text': head, 'is_video': True}, state, 12)
    assert video == photo + rk.RANKER_VIDEO_BONUS
    assert rk.RANKER_VIDEO_BONUS > 0  # default actually promotes video
