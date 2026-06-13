import pytest

from src.processor.topic_filter import is_off_topic


# Real titles sampled from the general-sport feeds that leak into this football bot.
OFF_TOPIC = [
    'Tenistas comemoram aumento da premiação de Wimbledon',
    'Spurs x Knicks: veja onde assistir ao jogo 5 das finais da NBA',
    'FC Porto vence Benfica em casa e passa para a frente final da Liga de basquetebol',
    'Europeus canoagem. Beatriz Fernandes e Inês Penetra na final C2 em bom dia luso',
    'Mboko ficará de fora de Wimbledon, mas espera voltar a jogar duplas com Serena',
    'F1: estamos ficando para trás em tudo, desabafa Verstappen após polêmica',
    'Red Bull domina etapa do MotoGP em Le Mans',
    'Seleção de vôlei vence e avança na Liga das Nações',
]

# Real football titles that MUST survive the filter (no false positives).
FOOTBALL = [
    'Benfica x Sporting: antevisão do jogo 1 da final do Campeonato Placard',
    'USA start World Cup in style - but will they finally join the elite?',
    'Pepa é o novo treinador do Estrela da Amadora para as próximas duas épocas',
    'Ancelotti estreia na Copa do Mundo no comando de um Brasil que sonha com o hexa',
    'Altos x Atlético-CE: veja onde assistir ao vivo, horário e prováveis escalações',  # Atlético != atletismo
    'Cristiano Ronaldo jogará a Copa do Mundo de 2026?',
    'Brilho de Garrincha, rebaixamentos e início da SAF: o que aconteceu com o Botafogo',
    'Náutico prepara mudanças no elenco com saídas na janela de transferências',  # Náutico (club), 'remo' not flagged
]


@pytest.mark.parametrize('title', OFF_TOPIC)
def test_off_topic_titles_are_flagged(title):
    assert is_off_topic(title) is True


@pytest.mark.parametrize('title', FOOTBALL)
def test_football_titles_pass(title):
    assert is_off_topic(title) is False


def test_checks_multiple_texts_original_and_translated():
    # original (en) clean football, translated (pt) carries the off-topic signal
    assert is_off_topic('clean football text', 'noticia sobre o torneio ATP de tenis') is True
    assert is_off_topic('Benfica vence', 'Benfica vence o Sporting') is False


def test_empty_and_none_safe():
    assert is_off_topic('', None) is False
