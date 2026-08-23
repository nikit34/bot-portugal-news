import pytest

from src.processor.audience_filter import is_off_audience


# Real captions the bot published to a page whose audience is 74.5% Portugal.
OFF_AUDIENCE = [
    'Libertadores: Palmeiras é escalado para enfrentar o Cerro Porteño. Verdão visita o time paraguaio nesta quarta-feira',
    'Vendido por R$ 27 milhões, zagueiro Igor Gomes aciona o Internacional na Justiça e tenta bloquear contas do clube',
    'Nubank esbarra na Prefeitura de SP para instalar letreiro de LED no estádio do Palmeiras',
    'Sob protestos, Vasco evita derrota em casa para Mirassol com golaço no fim',
    'A 1ª aplicação da regra “anti-bolinho” no Brasileirão! Anderson Daronco usou o sinal de X acima da cabeça',
    'PM classifica Cruzeiro x Flamengo pela Libertadores como jogo de risco',
    'Gabigol na saída de São Januário após a vitória do Santos por 3-0 sobre o Vasco',
    'Neymar tem 14 participações em gols nos seus últimos 13 jogos de Brasileirão',
    'Hugo Souza é acusado de homofobia após comentário sobre o São Paulo FC',
    'STJD concede efeito suspensivo a Victor Gabriel, punido por lesionar Gabriel Pec',
]

# Portugal-relevant or international football that MUST survive the gate.
ON_AUDIENCE = [
    '«Diogo Costa poderia ser o novo protagonista do Homem-Aranha...» As reações à vitória do FC Porto em Vila do Conde',
    'Rafael Nel é alvo de sondagens do Big 5. O jovem atacante ainda pode deixar Alvalade neste defeso',
    'Pedro Neto pode trocar de clube na Premier League: internacional português, no Chelsea desde 2024',
    '«O fato de o Benfica falar formalmente com o Bayern é a confirmação de que Palhinha admite voltar a Portugal»',
    'Árbitro diz que Messi deu trabalho na Copa, mas esfria polémica. O árbitro português João Pinheiro apitou o jogo',
    'Sem Julián Álvarez, Atlético Madrid vence o Málaga na rodada de abertura da La Liga',
    'Presidente da federação denuncia campanha miserável contra a Argentina',
    'Vitória SC 1-0 Nacional ao minuto',
    'Dinis Telehovschi renova contrato com o SL Benfica',
    'Cristiano Ronaldo jogará a Copa do Mundo de 2026?',
]


@pytest.mark.parametrize('text', OFF_AUDIENCE)
def test_brazil_domestic_is_dropped(text):
    assert is_off_audience(text) is True


@pytest.mark.parametrize('text', ON_AUDIENCE)
def test_portugal_and_international_survive(text):
    assert is_off_audience(text) is False


def test_portugal_signal_wins_over_brazil_signal():
    assert is_off_audience('Benfica fecha a contratação de um médio do Palmeiras por 12 milhões de euros') is False


def test_signal_is_read_across_all_texts():
    # Phase-1 passes the source text and the translation; a Portugal angle in either
    # one keeps the post.
    assert is_off_audience('Palmeiras signs a new midfielder', 'Palmeiras contrata médio do FC Porto') is False
    assert is_off_audience('Palmeiras signs a new midfielder', 'Palmeiras contrata médio do Bahia') is True


def test_empty_input_is_not_off_audience():
    assert is_off_audience() is False
    assert is_off_audience('', None) is False


@pytest.mark.parametrize('text', [
    'O internacional português foi convocado',
    'Atlético Madrid goleia o Betis',
    'Nacional da Madeira vence fora de casa',
    'Vitória de Guimarães prepara a receção ao Sporting',
])
def test_ambiguous_tokens_do_not_trigger_the_gate(text):
    assert is_off_audience(text) is False


@pytest.mark.parametrize('text,expected', [
    ('Benfica empresta João Rego ao Casa Pia até final da temporada', True),
    ('O árbitro português João Pinheiro apitou o jogo', True),
    ('Lazio chega a acordo com o Ajax e anuncia central da Eredivisie', False),
    ('Arsenal inicia defesa do título inglês com vitória sobre Coventry', False),
    ('', False),
])
def test_has_portugal_signal(text, expected):
    from src.processor.audience_filter import has_portugal_signal
    assert has_portugal_signal(text) is expected
