from collections import Counter

from src.static.settings import WEIGHT_KEYWORDS_THRESHOLD, MAX_COUNT_KEYWORDS


def extract_hashtags(doc):
    # Достаём из spaCy-разбора повторяющиеся существительные/имена собственные/
    # прилагательные и именованные сущности — это и есть хэштеги поста. Общая
    # логика для Facebook и Instagram, чтобы метки в обеих сетях совпадали.
    candidate_keywords = _candidate_keywords(doc)
    return _filter_keywords(candidate_keywords)


def hashtags_line(keywords):
    return ' '.join('#' + keyword for keyword in keywords)


def append_hashtags(text, keywords):
    line = hashtags_line(keywords)
    if not line:
        return text
    return text + '\n' + line


def _candidate_keywords(doc):
    candidate_words = [token.text for token in doc if token.pos_ in ['NOUN', 'PROPN', 'ADJ']]
    named_entities = [ent.text for ent in doc.ents]
    all_keywords = candidate_words + named_entities
    keyword_freq = Counter(all_keywords)
    return keyword_freq.most_common(MAX_COUNT_KEYWORDS)


def _filter_keywords(candidate_keywords):
    keywords = []
    for item in candidate_keywords:
        if item[1] >= WEIGHT_KEYWORDS_THRESHOLD:
            raw_keyword = item[0]
            if len(raw_keyword) > 2:
                keyword = raw_keyword.replace('-', '').replace(' ', '').lower()
                keywords.append(keyword)
    return keywords
