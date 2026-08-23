import re
import logging
import unicodedata

logger = logging.getLogger('app')

# The page audience is 74.5% Portugal; the feeds also carry Brazilian domestic
# football, which that audience does not follow. A post is dropped when it carries a
# Brazil-domestic signal AND no Portugal signal — so Portugal-relevant transfers and
# international competitions survive even when a Brazilian club is on the other side.
#
# Ambiguous tokens are deliberately absent from the Brazil list: 'internacional'
# (also 'internacional português'), 'vitória' and 'nacional' (Portuguese clubs too),
# 'santos' (common surname), 'atlético' (Atlético Madrid), 'porto' (Porto Alegre),
# 'remo' (rowing), 'sport' and 'américa'.
_BRAZIL_TERMS = [
    # competitions and governing bodies
    'brasileirao', 'campeonato brasileiro', 'copa do brasil', 'libertadores',
    'sul-americana', 'sudamericana', 'paulistao', 'campeonato paulista',
    'campeonato carioca', 'campeonato mineiro', 'campeonato gaucho', 'cbf', 'stjd',
    # clubs
    'flamengo', 'palmeiras', 'corinthians', 'cruzeiro', 'gremio', 'fluminense',
    'botafogo', 'vasco', 'sao paulo', 'bahia', 'fortaleza', 'mirassol', 'juventude',
    'bragantino', 'athletico-pr', 'atletico-mg', 'atletico mineiro', 'coritiba',
    'goias', 'cuiaba', 'chapecoense', 'ponte preta', 'nautico', 'paysandu',
    'criciuma', 'avai', 'figueirense', 'novorizontino', 'sport recife', 'ceara',
    'santos fc', 'sc internacional',
    # stadiums and nicknames
    'maracana', 'mineirao', 'morumbi', 'neo quimica arena', 'sao januario',
    'allianz parque', 'nubank parque', 'beira-rio', 'vila belmiro', 'arena mrv',
    'verdao', 'timao', 'mengao',
]

_PORTUGAL_TERMS = [
    # nationality and geography
    'portugal', 'portugues', 'portuguesa', 'portugueses', 'portuguesas', 'luso',
    'lisboa', 'madeira', 'acores', 'coimbra',
    # clubs
    'benfica', 'sporting', 'fc porto', 'sc braga', 'braga', 'vitoria sc',
    'vitoria de guimaraes', 'guimaraes', 'boavista', 'rio ave', 'famalicao',
    'arouca', 'gil vicente', 'casa pia', 'moreirense', 'estoril', 'farense',
    'estrela da amadora', 'alverca', 'tondela', 'penafiel', 'santa clara',
    'maritimo', 'chaves', 'nacional da madeira', 'uniao de leiria', 'leixoes',
    'academico de viseu', 'portimonense', 'feirense', 'torreense', 'vizela',
    # competitions
    'primeira liga', 'liga portugal', 'liga betclic', 'taca de portugal',
    'taca da liga', 'allianz cup', 'supertaca', 'liga 3', 'campeonato de portugal',
    'selecao nacional', 'selecao portuguesa', 'fpf',
    # venues and people
    'alvalade', 'estadio da luz', 'dragao', 'jamor', 'cristiano ronaldo',
    'ruben amorim', 'roberto martinez', 'mourinho', 'jorge jesus', 'bruno lage',
]

_BRAZIL_PATTERN = re.compile(r'\b(' + '|'.join(_BRAZIL_TERMS) + r')\b')
_PORTUGAL_PATTERN = re.compile(r'\b(' + '|'.join(_PORTUGAL_TERMS) + r')\b')
# Amounts in Brazilian reais are an unambiguous domestic-market signal.
_BRL_PATTERN = re.compile(r'r\$\s*\d')


def _normalize(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in text if not unicodedata.combining(char))


def has_portugal_signal(*texts):
    for text in texts:
        if not text:
            continue
        match = _PORTUGAL_PATTERN.search(_normalize(text))
        if match:
            logger.debug(f"[AudienceFilter] Portugal signal (matched '{match.group(1)}')")
            return True
    return False


def is_off_audience(*texts):
    # A Portugal signal anywhere wins over a Brazil signal anywhere, so the gate can
    # only remove posts with no Portugal angle at all.
    if has_portugal_signal(*texts):
        return False

    for text in texts:
        if not text:
            continue
        normalized = _normalize(text)
        match = _BRAZIL_PATTERN.search(normalized) or _BRL_PATTERN.search(normalized)
        if match:
            logger.debug(f"[AudienceFilter] off-audience (matched '{match.group(0)}')")
            return True

    return False
