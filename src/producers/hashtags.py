from collections import Counter

from src.static.settings import (
    WEIGHT_KEYWORDS_THRESHOLD,
    MAX_COUNT_KEYWORDS,
    HASHTAG_ENTITY_BIAS_ENABLED,
    HASHTAG_NICHE_TAG,
)

# pt_core_news_sm (WikiNER) даёт метки {LOC, MISC, ORG, PER}. Клуб/игрок — это
# ORG/PER; именно их полезно поднимать в хэштеги (тематич. матч поста к интересам).
_ENTITY_LABELS = ('ORG', 'PER')


def extract_hashtags(doc, max_count=MAX_COUNT_KEYWORDS):
    # Хэштеги поста: опц. нишевая метка -> распознанные сущности (клуб/игрок) ->
    # частотные существительные/имена/прилагательные. Общая логика для FB и IG;
    # max_count разный (на FB режем жёстче — там >5 меток выглядит спамом).
    keywords = []
    if HASHTAG_NICHE_TAG:
        niche = _clean(HASHTAG_NICHE_TAG)
        if niche:
            keywords.append(niche)
    if HASHTAG_ENTITY_BIAS_ENABLED:
        for ent in _entity_keywords(doc):
            if ent not in keywords:
                keywords.append(ent)
    for kw in _frequency_keywords(doc):
        if kw not in keywords:
            keywords.append(kw)
    return keywords[:max_count]


def hashtags_line(keywords):
    return ' '.join('#' + keyword for keyword in keywords)


def append_hashtags(text, keywords):
    line = hashtags_line(keywords)
    if not line:
        return text
    return text + '\n' + line


def _entity_keywords(doc):
    # Распознанные ORG/PER — допускаем даже при единичном упоминании (имена в
    # коротких новостях редко повторяются), сохраняя порядок появления в тексте.
    out = []
    for ent in doc.ents:
        if getattr(ent, 'label_', '') in _ENTITY_LABELS:
            kw = _clean(ent.text)
            if kw and kw not in out:
                out.append(kw)
    return out


def _frequency_keywords(doc):
    candidate_words = [token.text for token in doc if token.pos_ in ('NOUN', 'PROPN', 'ADJ')]
    named_entities = [ent.text for ent in doc.ents]
    keyword_freq = Counter(candidate_words + named_entities)
    out = []
    for raw_keyword, count in keyword_freq.most_common():
        if count >= WEIGHT_KEYWORDS_THRESHOLD:
            kw = _clean(raw_keyword)
            if kw:
                out.append(kw)
    return out


def _clean(raw_keyword):
    keyword = raw_keyword.replace('-', '').replace(' ', '').lower()
    return keyword if len(keyword) > 2 else ''
