import pytest

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


def test_portugal_bonus_lifts_score(monkeypatch):
    # The audience gate only removes Brazil-domestic posts; without this bonus an
    # international story with no Portugal angle can take the single daily slot.
    import src.processor.ranker as rk
    monkeypatch.setattr(rk, 'RANKER_PT_BONUS', 1.5)
    state = {'sources': {}, 'hours': {}}
    pt = 'Benfica fecha a contratacao de um medio internacional para a Liga Betclic'
    intl = 'Lazio chega a acordo com o Ajax e anuncia central da Eredivisie por 12M'
    pt_score = candidate_score({'head': pt, 'source': 's', 'text': pt}, state, 12)
    intl_score = candidate_score({'head': intl, 'source': 's', 'text': intl}, state, 12)
    assert pt_score > intl_score
    assert pt_score - intl_score == pytest.approx(
        1.5 + rk._length_bonus(pt) - rk._length_bonus(intl))


def test_portugal_bonus_reads_the_body_not_only_the_head(monkeypatch):
    # head is truncated to 50 chars, so a Portugal angle further into the text must
    # still count.
    import src.processor.ranker as rk
    monkeypatch.setattr(rk, 'RANKER_PT_BONUS', 1.5)
    state = {'sources': {}, 'hours': {}}
    head = 'Lazio chega a acordo com o Ajax e anuncia cent'
    body = head + ' que foi apontado ao Benfica durante todo o defeso'
    with_angle = candidate_score({'head': head, 'source': 's', 'text': body}, state, 12)
    without = candidate_score({'head': head, 'source': 's', 'text': head}, state, 12)
    assert with_angle - without == pytest.approx(1.5)


def test_portugal_bonus_is_off_by_default():
    import src.processor.ranker as rk
    assert rk.RANKER_PT_BONUS == 0.0
