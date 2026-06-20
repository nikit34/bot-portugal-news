import re

from src.processor.caption_guard import scrub_caption
from src.producers.cta import build_cta
from src.static.settings import HOOK_FIRST_ENABLED, CTA_ENABLED

# Метки сущностей pt_core_news_sm, которыми «якорим» сильный лид (клуб/игрок).
_ENTITY_LABELS = ('ORG', 'PER')
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?…])\s+')


def trunc_str(text, max_length):
    return text[:max_length] + '...' if len(text) > max_length else text


def hook_first(text, entity_texts):
    # Консервативный hook-first: если ПЕРВОЕ предложение НЕ содержит сущности
    # (клуб/игрок), а более позднее — содержит, переносим то предложение в начало
    # (и убираем со старого места, чтобы не задвоить). Ничего НЕ переписываем —
    # без платной LLM это рискованно. Нет сущностей / одно предложение => без изменений.
    if not text or not entity_texts:
        return text
    sentences = _SENTENCE_SPLIT.split(text.strip())
    if len(sentences) < 2:
        return text

    def has_entity(sentence):
        low = sentence.lower()
        return any(e.lower() in low for e in entity_texts if e)

    if has_entity(sentences[0]):
        return text
    for i in range(1, len(sentences)):
        if has_entity(sentences[i]):
            promoted = sentences.pop(i)
            sentences.insert(0, promoted)
            return ' '.join(sentences)
    return text


def prepare_body(text, doc, max_length):
    # Общая подготовка тела подписи перед хэштегами: чистим bait/крик (caption_guard),
    # опц. выносим entity-first лид (hook_first), опц. добавляем живой вопрос-CTA,
    # затем режем по лимиту платформы (резервируя место под CTA, чтобы не превысить).
    body = scrub_caption(text)
    if HOOK_FIRST_ENABLED and doc is not None:
        entity_texts = [e.text for e in doc.ents if getattr(e, 'label_', '') in _ENTITY_LABELS]
        body = hook_first(body, entity_texts)
    cta = build_cta(doc) if (CTA_ENABLED and doc is not None) else ''
    body = trunc_str(body, max(0, max_length - (len(cta) + 2)) if cta else max_length)
    if cta:
        body = body + '\n\n' + cta
    return body
