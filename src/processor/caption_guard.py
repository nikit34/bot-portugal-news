import re
import logging

from src.processor.content_filter import _normalize
from src.static.bait_blocklist import CTA_BAIT, CLICKBAIT
from src.static.settings import CAPTION_GUARD_ENABLED

logger = logging.getLogger('app')

# Компилируем на нормализованную форму (без акцентов/регистра, leet разраскрыт).
_CTA = [re.compile(p) for p in CTA_BAIT]
_CLICKBAIT = [re.compile(p) for p in CLICKBAIT]


def _matches_any(normalized, patterns):
    return any(p.search(normalized) for p in patterns)


def _is_screaming(word):
    # «Крик»: слово с >=3 буквами, все заглавные (есть регистр и он весь верхний).
    letters = [c for c in word if c.isalpha()]
    return len(letters) >= 3 and word == word.upper() and word != word.lower()


def _dampen_caps(line):
    # Гасим КАПС-крик: опускаем в нижний регистр пробег из >=2 подряд капс-слов
    # (так кричат) или одиночное очень длинное капс-слово (>=8 букв). Одиночные
    # короткие капсы (FC, SL, VAR, UEFA, аббревиатуры) НЕ трогаем.
    words = line.split(' ')
    flags = [_is_screaming(w) for w in words]
    out, i, n = [], 0, len(words)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]:
                j += 1
            run_len = j - i
            for k in range(i, j):
                letters = sum(c.isalpha() for c in words[k])
                out.append(words[k].lower() if (run_len >= 2 or letters >= 8) else words[k])
            i = j
        else:
            out.append(words[i])
            i += 1
    return ' '.join(out)


def scrub_caption(text):
    """Вычистить исходящую подпись от engagement-bait и КАПС-крика.

    Удаляет строки-CTA («marque um amigo», «comente SIM», «share to win»),
    гасит крик заглавными. Матч — по нормализованной форме, РЕЗ — по оригиналу,
    поэтому акценты и регистр публикуемого текста сохраняются. Кликбейт-фразы
    НЕ вырезаются (могут вести реальный заголовок) — на них смотрит clickbait_score.
    """
    if not CAPTION_GUARD_ENABLED or not text:
        return text
    kept = []
    for line in text.split('\n'):
        normalized = _normalize(line)
        if normalized and _matches_any(normalized, _CTA):
            continue  # самостоятельная CTA-строка — выкидываем целиком
        kept.append(_dampen_caps(line))
    cleaned = re.sub(r'\n{3,}', '\n\n', '\n'.join(kept)).strip()
    # Если вычистили всё (подпись была чистым CTA) — не публикуем пустоту: вернём
    # исходный текст лишь со снятым криком, чтобы пост не остался без подписи.
    return cleaned if cleaned else _dampen_caps(text).strip()


def clickbait_score(text):
    """Штраф 0..1 за bait/кликбейт/крик в подписи — для ранжирования кандидатов.

    Не мутирует текст. Чем выше, тем «спамнее» выглядит пост (ниже в ранкере).
    """
    if not text:
        return 0.0
    normalized = _normalize(text)
    hits = sum(1 for p in _CTA if p.search(normalized))
    hits += sum(1 for p in _CLICKBAIT if p.search(normalized))
    words = text.split()
    caps = sum(1 for w in words if _is_screaming(w))
    caps_ratio = caps / len(words) if words else 0.0
    return min(1.0, 0.34 * hits + min(0.4, caps_ratio))
