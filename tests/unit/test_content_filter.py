from src.processor.content_filter import is_blocked_content, strip_promo, _normalize


def test_blocks_profanity():
    assert is_blocked_content("vai pro caralho arbitro")
    assert is_blocked_content("que porra de jogo")
    assert is_blocked_content("isso e uma merda completa")


def test_blocks_obfuscated_profanity():
    assert is_blocked_content("vai pro car@lho")          # @ -> a
    assert is_blocked_content("que p0rra e essa")          # 0 -> o
    assert is_blocked_content("caralhooooo que golo")      # схлопывание повторов


def test_blocks_english_profanity():
    assert is_blocked_content("what the fuck happened there")
    assert is_blocked_content("this is bullshit")


def test_blocks_gambling_ads():
    assert is_blocked_content("Aposte na Bet365 e ganhe bonus agora")
    assert is_blocked_content("melhor cassino online do brasil")
    assert is_blocked_content("use o codigo promocional para deposito")


def test_does_not_block_clean_football_news():
    assert not is_blocked_content(
        "Benfica venceu o Porto por 2 a 1 no estadio da Luz, golo de Otamendi"
    )
    assert not is_blocked_content("Cristiano Ronaldo marcou um hat-trick historico")


def test_does_not_block_puto_pt_pt():
    # "puto" в PT-PT = "пацан", не должно блокироваться (блокируем только "puta")
    assert not is_blocked_content("O puto marcou um golo lindo na estreia")


def test_checks_all_texts():
    # оригинал чистый, перевод с матом -> блок
    assert is_blocked_content("clean english headline", "texto com caralho aqui")
    # все чистые -> не блок
    assert not is_blocked_content("clean english headline", "noticia limpa de futebol")


def test_handles_empty_and_none():
    assert not is_blocked_content("", None)


def test_normalize_strips_accents_and_leet():
    assert _normalize("CAR@LHO") == "caralho"
    assert _normalize("bônus") == "bonus"


def test_strip_promo_removes_footer_keeps_attribution():
    text = "Benfica venceu o Porto por 2 a 1\n🗞 @geglobo\n| AO VIVO | Inscreva-se no canal"
    out = strip_promo(text)
    assert "Benfica venceu" in out
    assert "@geglobo" in out            # легитимная атрибуция сохраняется
    assert "Inscreva-se" not in out
    assert "AO VIVO" not in out


def test_strip_promo_removes_telegram_promo():
    out = strip_promo("Noticia importante de futebol\nCanais no Telegram para te fortalecerem")
    assert "Noticia importante" in out
    assert "Telegram" not in out


def test_strip_promo_keeps_clean_text():
    text = "Cristiano Ronaldo marcou um hat-trick\nGolo decisivo aos 90 minutos"
    assert strip_promo(text) == text


def test_strip_promo_empty():
    assert strip_promo("") == ""
