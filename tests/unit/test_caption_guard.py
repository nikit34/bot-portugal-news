from src.processor.caption_guard import scrub_caption, clickbait_score, _dampen_caps


def test_clean_pt_headline_unchanged():
    text = "Benfica vence o Porto por 2-1 no clássico da Luz"
    assert scrub_caption(text) == text


def test_drops_pt_cta_bait_lines():
    text = "Benfica vence o Porto por 2-1\nComente SIM se concorda\nMarque um amigo benfiquista"
    out = scrub_caption(text)
    assert "Benfica vence o Porto" in out
    assert "Comente" not in out
    assert "Marque um amigo" not in out


def test_drops_en_cta_bait_lines():
    text = "Ronaldo scores again\nTag a friend who loves football\nLike if you agree"
    out = scrub_caption(text)
    assert "Ronaldo scores again" in out
    assert "Tag a friend" not in out
    assert "Like if" not in out


def test_drops_share_to_win():
    out = scrub_caption("Sorteio da camisola\nCompartilhe para ganhar uma camisa")
    assert "Compartilhe para ganhar" not in out
    assert "Sorteio da camisola" in out


def test_dampens_all_caps_screaming_run():
    # Пробег из 2+ капс-слов гасится; первое предложение остаётся читаемым.
    out = scrub_caption("BENFICA CAMPEÃO NACIONAL e a festa continua")
    assert "BENFICA CAMPEÃO" not in out
    assert "benfica campeão nacional" in out.lower()


def test_keeps_short_acronyms_and_single_caps():
    # FC, SL, VAR, UEFA (одиночные/короткие) — не трогаем (легитимные аббревиатуры).
    text = "O VAR anulou o golo do FC Porto na final da UEFA"
    assert scrub_caption(text) == text


def test_legit_emotive_word_in_quote_not_stripped():
    # Одиночные эмоциональные слова (incrível/chocante) НЕ являются паттернами.
    text = "Treinador: foi um jogo incrível e o resultado é chocante"
    assert scrub_caption(text) == text


def test_clickbait_phrase_not_stripped_but_scored():
    text = "Você não vai acreditar no que o Benfica fez ontem à noite"
    # фраза-кликбейт остаётся в тексте (ведёт заголовок), но получает штраф
    assert scrub_caption(text) == text
    assert clickbait_score(text) > 0


def test_clickbait_score_clean_is_zero():
    assert clickbait_score("Benfica vence o Porto por 2-1 no clássico") == 0.0


def test_clickbait_score_bounded():
    spam = "COMENTE SIM MARQUE UM AMIGO COMPARTILHE você não vai acreditar tag a friend"
    assert 0.0 < clickbait_score(spam) <= 1.0


def test_pure_bait_falls_back_to_dampened_original():
    # Подпись из одного CTA не должна стать пустой — возвращаем хотя бы de-screamed текст.
    out = scrub_caption("MARQUE UM AMIGO AGORA")
    assert out  # не пусто
    assert out == _dampen_caps("MARQUE UM AMIGO AGORA").strip()


def test_empty_input():
    assert scrub_caption('') == ''
    assert clickbait_score('') == 0.0
