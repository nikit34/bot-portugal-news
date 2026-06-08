import re
import logging
import unicodedata

from src.static.blocklist import BLOCKLIST, PROMO_FOOTERS

logger = logging.getLogger('app')

_PROMO_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in PROMO_FOOTERS]

# Раскрытие частой обфускации (car@lho -> caralho, p0rra -> porra, $ -> s)
_LEET = str.maketrans({'@': 'a', '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '$': 's'})

_PATTERNS = [re.compile(pattern) for pattern in BLOCKLIST]


def _normalize(text):
    text = text.lower().translate(_LEET)
    # снять диакритику: ç->c, ã->a, ô->o ... (чтобы паттерны можно было писать без акцентов)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(char for char in text if not unicodedata.combining(char))
    # схлопнуть 3+ повторов символа: caralhooo -> caralho
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    return text


def is_blocked_content(*texts):
    for text in texts:
        if not text:
            continue
        normalized = _normalize(text)
        for pattern in _PATTERNS:
            if pattern.search(normalized):
                logger.debug(f"[ContentFilter] Blocked by pattern '{pattern.pattern}'")
                return True
    return False


def strip_promo(text):
    if not text:
        return text
    kept = [line for line in text.split('\n')
            if not any(pattern.search(line) for pattern in _PROMO_PATTERNS)]
    cleaned = re.sub(r'\n{3,}', '\n\n', '\n'.join(kept)).strip()
    return cleaned
