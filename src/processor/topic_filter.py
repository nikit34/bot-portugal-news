import re
import logging
import unicodedata

logger = logging.getLogger('app')

# This is a FOOTBALL channel, but several RSS feeds are general-sport (rtp/desporto,
# gazetaesportiva, ge.globo, ...) and leak F1 / tennis / NBA / etc. We drop a post
# when its text carries a strong non-football SPORT signal. The list is deliberately
# high-precision — only sport/competition names that don't appear in football copy —
# so it won't nuke football (e.g. 'atletismo' won't match the club 'Atlético', and
# ambiguous tokens like 'set', 'gp', 'giro', 'remo', 'tour' are intentionally absent).
_OFF_TOPIC_TERMS = [
    # tennis
    'tennis', 'tenis', 'tenista', 'tenistas', 'wimbledon', 'roland garros', 'atp', 'wta', 'grand slam',
    # motorsport
    'formula 1', 'f1', 'grande premio', 'grand prix', 'pole position', 'motogp', 'automobilismo',
    # basketball
    'basquete', 'basquetebol', 'basketball', 'nba',
    # volleyball
    'volei', 'voleibol', 'volleyball',
    # combat
    'mma', 'ufc',
    # cycling / swimming / athletics / gymnastics
    'ciclismo', 'cycling', 'natacao', 'swimming', 'atletismo', 'athletics', 'ginastica', 'gymnastics',
    # misc non-football sports
    'canoagem', 'canoeing', 'surf', 'surfe', 'surfing', 'skate', 'skateboard',
    'handebol', 'andebol', 'handball', 'raguebi', 'rugby', 'golfe', 'golf',
]

# Match whole words/phrases only, against accent-stripped lowercase text.
_OFF_TOPIC_PATTERN = re.compile(r'\b(' + '|'.join(_OFF_TOPIC_TERMS) + r')\b')


def _normalize(text):
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in text if not unicodedata.combining(char))


def is_off_topic(*texts):
    # Checks both the original and the translated text so a signal in either language
    # is caught. Returns True if the post is about a non-football sport.
    for text in texts:
        if not text:
            continue
        match = _OFF_TOPIC_PATTERN.search(_normalize(text))
        if match:
            logger.debug(f"[TopicFilter] off-topic (matched '{match.group(1)}')")
            return True
    return False
