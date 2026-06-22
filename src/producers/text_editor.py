from src.processor.caption_guard import scrub_caption
from src.producers.cta import build_cta
from src.static.settings import CTA_ENABLED


def trunc_str(text, max_length):
    return text[:max_length] + '...' if len(text) > max_length else text


def prepare_body(text, doc, max_length):
    # Общая подготовка тела подписи перед хэштегами: чистим bait/крик (caption_guard),
    # опц. добавляем живой вопрос-CTA, затем режем по лимиту платформы (резервируя
    # место под CTA, чтобы не превысить).
    body = scrub_caption(text)
    cta = build_cta(doc) if (CTA_ENABLED and doc is not None) else ''
    body = trunc_str(body, max(0, max_length - (len(cta) + 2)) if cta else max_length)
    if cta:
        body = body + '\n\n' + cta
    return body
