from src.producers.hashtags import extract_hashtags, append_hashtags
from src.producers.instagram.producer import instagram_prepare_post
from src.producers.facebook.producer import facebook_prepare_post


class _Tok:
    def __init__(self, text, pos):
        self.text = text
        self.pos_ = pos


class _Ent:
    def __init__(self, text):
        self.text = text


class _Doc:
    # Minimal stand-in for a spaCy Doc: iterable of tokens + .ents
    def __init__(self, tokens, ents=()):
        self._tokens = tokens
        self.ents = list(ents)

    def __iter__(self):
        return iter(self._tokens)


def test_extract_hashtags_keeps_repeated_keywords():
    # Benfica/golo appear twice (>= WEIGHT_KEYWORDS_THRESHOLD), 'e' is a non-content
    # POS and dropped, 'no' is too short (<= 2 chars).
    tokens = [
        _Tok('Benfica', 'PROPN'), _Tok('Benfica', 'PROPN'),
        _Tok('golo', 'NOUN'), _Tok('golo', 'NOUN'),
        _Tok('no', 'NOUN'), _Tok('no', 'NOUN'),
        _Tok('e', 'CCONJ'), _Tok('e', 'CCONJ'),
    ]
    tags = extract_hashtags(_Doc(tokens))

    assert 'benfica' in tags
    assert 'golo' in tags
    assert 'no' not in tags
    assert 'e' not in tags


def test_extract_hashtags_drops_singletons():
    tokens = [_Tok('Sporting', 'PROPN'), _Tok('vitoria', 'NOUN')]
    assert extract_hashtags(_Doc(tokens)) == []


def test_append_hashtags_empty_returns_text_unchanged():
    assert append_hashtags('Notícia do dia', []) == 'Notícia do dia'


def test_append_hashtags_joins_with_newline():
    assert append_hashtags('texto', ['porto', 'golo']) == 'texto\n#porto #golo'


def test_instagram_prepare_post_comment_mode_default():
    # Default mode: clean caption, hashtags returned as the first-comment string.
    doc = _Doc([_Tok('Porto', 'PROPN'), _Tok('Porto', 'PROPN')])
    caption, comment = instagram_prepare_post('FC Porto venceu', doc)

    assert caption == 'FC Porto venceu'
    assert '#porto' in comment


def test_instagram_prepare_post_caption_mode_toggle(monkeypatch):
    # Toggle off: hashtags go back into the caption, no first comment.
    import src.producers.instagram.producer as ig
    monkeypatch.setattr(ig, 'INSTAGRAM_HASHTAGS_AS_COMMENT', False)
    doc = _Doc([_Tok('Porto', 'PROPN'), _Tok('Porto', 'PROPN')])
    caption, comment = ig.instagram_prepare_post('FC Porto venceu', doc)

    assert caption.startswith('FC Porto venceu')
    assert '#porto' in caption
    assert comment == ''


def test_facebook_prepare_post_still_appends_hashtags():
    # Refactor parity: FB caption keeps the same hashtag behaviour after the
    # keyword logic moved into the shared hashtags module.
    doc = _Doc([_Tok('Liga', 'PROPN'), _Tok('Liga', 'PROPN')])
    out = facebook_prepare_post('Resumo da jornada', doc)

    assert out.startswith('Resumo da jornada')
    assert '#liga' in out
