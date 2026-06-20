from src.producers.cta import build_cta, _TEMPLATES, _FORBIDDEN


class _Ent:
    def __init__(self, text, label):
        self.text = text
        self.label_ = label


class _Doc:
    def __init__(self, ents=()):
        self.ents = list(ents)


def test_no_template_contains_engagement_bait():
    # The library IS the guard: not a single template may carry a bait phrasing.
    for tmpl in _TEMPLATES:
        assert _FORBIDDEN.search(tmpl) is None
        assert '{entity}' in tmpl  # every question is anchored to a real entity


def test_build_cta_substitutes_entity():
    cta = build_cta(_Doc([_Ent('Benfica', 'ORG')]))
    assert 'Benfica' in cta
    assert _FORBIDDEN.search(cta) is None


def test_build_cta_empty_without_entities():
    assert build_cta(_Doc([])) == ''
    assert build_cta(_Doc([_Ent('Lisboa', 'LOC')])) == ''  # LOC is not an anchor


def test_build_cta_is_deterministic_per_entity():
    doc = _Doc([_Ent('Cristiano Ronaldo', 'PER')])
    assert build_cta(doc) == build_cta(doc)


def test_build_cta_varies_across_entities():
    # Different entities can map to different templates (entity-substituted variety).
    a = build_cta(_Doc([_Ent('Benfica', 'ORG')]))
    b = build_cta(_Doc([_Ent('Sporting Clube de Portugal', 'ORG')]))
    assert a and b  # both produce a question
