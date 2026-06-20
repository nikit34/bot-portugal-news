import os
import re
import logging

from PIL import Image, ImageDraw

from src.producers.story_overlay import (
    _font, _cover, _contain, _bottom_gradient, _wrap, extract_headline,
    _ACCENT, _BRAND_COLOR,
)
from src.static.settings import CARDS_ENABLED, STORY_OVERLAY_BRAND

logger = logging.getLogger('app')

# 4:5 — самый «высокий» допустимый формат для ленты (занимает больше экрана).
CARD_W, CARD_H = 1080, 1350

_MARGIN = 72
_HEADLINE_SIZE = 70
_LINE_H = 84
_MAX_LINES = 5
_FOOTER_PAD = 110

# Метки сущностей pt_core_news_sm: клуб (ORG) / игрок (PER).
_ENTITY_LABELS = ('ORG', 'PER')

# Денежная сумма трансфера: «€80M», «80 milhões», «80M€», «EUR 80 milhões», «€12,5M».
_MONEY = re.compile(
    r'(?:€|eur\b|euros?)\s?\d[\d.,]*\s?(?:m|mi|mil|milh\w+)?'
    r'|\d[\d.,]*\s?milh\w+'
    r'|\d[\d.,]*\s?m€',
    re.IGNORECASE,
)


def is_transfer_card_eligible(text, doc):
    # Карточку v1 рендерим ТОЛЬКО для новостей про деньги/трансфер (сумма однозначна,
    # в отличие от счёта, где направление неочевидно) И при наличии клуба/игрока.
    if not text or not _MONEY.search(text):
        return False
    return any(getattr(ent, 'label_', '') in _ENTITY_LABELS for ent in getattr(doc, 'ents', []))


def render_card(src_path, headline, out_path=None, kicker='MERCADO', brand=STORY_OVERLAY_BRAND):
    """Собрать оригинальную 4:5-карточку с прожжённым заголовком (наш value-add
    против unoriginal-content демоута). None при любой ошибке (грузим оригинал)."""
    try:
        with Image.open(src_path) as raw:
            src = raw.convert('RGB')

        canvas = _cover(src, CARD_W, CARD_H)
        canvas = Image.blend(canvas, Image.new('RGB', canvas.size, (0, 0, 0)), 0.30)
        fg = _contain(src, CARD_W, int(CARD_H * 0.62))
        canvas.paste(fg, ((CARD_W - fg.width) // 2, _MARGIN))
        canvas = Image.composite(
            Image.new('RGB', canvas.size, (0, 0, 0)), canvas, _bottom_gradient(CARD_W, CARD_H))

        draw = ImageDraw.Draw(canvas)
        head_font = _font(_HEADLINE_SIZE)
        lines = _wrap(draw, headline, head_font, CARD_W - 2 * _MARGIN)

        kicker_font = _font(40)
        kicker_h = 62
        bar_h = 38
        block_h = bar_h + kicker_h + _LINE_H * len(lines)
        y = CARD_H - _FOOTER_PAD - block_h

        draw.rectangle([_MARGIN, y, _MARGIN + 96, y + 12], fill=_ACCENT)
        y += bar_h
        label = (brand.upper() + ' · ' + kicker) if brand else kicker
        draw.text((_MARGIN, y), label, font=kicker_font, fill=_BRAND_COLOR)
        y += kicker_h
        for line in lines:
            draw.text((_MARGIN + 3, y + 3), line, font=head_font, fill=(0, 0, 0))  # тень
            draw.text((_MARGIN, y), line, font=head_font, fill=(255, 255, 255))
            y += _LINE_H

        if out_path is None:
            out_path = os.path.splitext(src_path)[0] + '.card.jpg'
        canvas.save(out_path, format='JPEG', quality=88)
        return out_path
    except Exception as e:
        logger.warning(f"[cards] render failed for {src_path}: {e}")
        return None


def build_card_image(src_path, message, doc):
    """Оригинальная карточка для трансферной новости. None => публикуем как есть."""
    if not CARDS_ENABLED:
        return None
    if not src_path or not os.path.isfile(src_path):
        return None
    if not is_transfer_card_eligible(message, doc):
        return None
    headline = extract_headline(message)
    if not headline:
        return None
    return render_card(src_path, headline)
