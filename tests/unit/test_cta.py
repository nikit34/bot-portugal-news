import pytest

import src.producers.cta as cta


class _Ent:
    def __init__(self, text, label):
        self.text = text
        self.label_ = label


class _Doc:
    def __init__(self, ents=(), text=None):
        self.ents = list(ents)
        if text is not None:
            self.text = text


@pytest.fixture(autouse=True)
def _full_emission(monkeypatch):
    # Content tests assert a CTA is produced; isolate them from the fractional gate
    # by forcing full emission. The gate itself is covered by test_emission_gate_*.
    monkeypatch.setattr(cta, 'CTA_EMISSION_RATE', 1.0)


def test_no_template_contains_engagement_bait():
    # The library IS the guard: not a single template may carry a bait phrasing.
    for tmpl in cta._TEMPLATES:
        assert cta._FORBIDDEN.search(tmpl) is None
        assert '{entity}' in tmpl  # every question is anchored to a real entity


def test_build_cta_substitutes_entity():
    out = cta.build_cta(_Doc([_Ent('Benfica', 'ORG')]))
    assert 'Benfica' in out
    assert cta._FORBIDDEN.search(out) is None


def test_build_cta_empty_without_entities():
    assert cta.build_cta(_Doc([])) == ''
    assert cta.build_cta(_Doc([_Ent('Lisboa', 'LOC')])) == ''  # LOC is not an anchor


def test_build_cta_is_deterministic_per_post():
    doc = _Doc([_Ent('Cristiano Ronaldo', 'PER')], text='Cristiano Ronaldo marcou dois golos')
    assert cta.build_cta(doc) == cta.build_cta(doc)


def test_build_cta_varies_by_post_text_for_same_entity():
    # The same recurring entity gets DIFFERENT questions across posts (template is
    # picked by post text), which is what defuses verbatim-repetition demotion risk.
    ent = [_Ent('Benfica', 'ORG')]
    seen = set()
    posts = [
        'Benfica vence o Porto por 2-1 no classico da Luz',
        'Benfica anuncia reforco para o meio-campo nesta janela',
        'Benfica empata fora e perde a lideranca da liga',
        'Benfica renova com o capitao ate 2030 oficialmente',
    ]
    for text in posts:
        seen.add(cta.build_cta(_Doc(ent, text=text)))
    assert len(seen) >= 2          # at least two distinct questions across posts
    assert all('Benfica' in q for q in seen)


def test_emission_gate_off_and_full(monkeypatch):
    ent = [_Ent('Benfica', 'ORG')]
    monkeypatch.setattr(cta, 'CTA_EMISSION_RATE', 0.0)
    assert all(cta.build_cta(_Doc(ent, text=f'post numero {i}')) == '' for i in range(20))
    monkeypatch.setattr(cta, 'CTA_EMISSION_RATE', 1.0)
    assert all(cta.build_cta(_Doc(ent, text=f'post numero {i}')) for i in range(20))


def test_emission_gate_partial_fires_on_a_fraction(monkeypatch):
    ent = [_Ent('Benfica', 'ORG')]
    monkeypatch.setattr(cta, 'CTA_EMISSION_RATE', 0.5)
    out = [cta.build_cta(_Doc(ent, text=f'post numero {i} sobre o jogo de ontem')) for i in range(40)]
    emitted = [o for o in out if o]
    assert 0 < len(emitted) < 40   # some posts get a CTA, some don't
