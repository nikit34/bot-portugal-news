import os
import re
import logging

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.static.settings import (
    STORY_TEXT_OVERLAY_ENABLED,
    STORY_OVERLAY_BRAND,
    STORY_HEADLINE_MAX_CHARS,
)

logger = logging.getLogger('app')

# Stories рендерятся в портрет 9:16; готовим картинку сразу в этом размере, чтобы
# текст лёг предсказуемо (иначе Meta сама кропит/леттербоксит как захочет).
STORY_W, STORY_H = 1080, 1920

# DejaVu Sans зашит в репо (src/static/fonts) — системные шрифты на CI-рунере
# ненадёжны, а у DejaVu полное покрытие португальской диакритики (á ç ã õ ê …).
_FONT_BOLD = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'fonts', 'DejaVuSans-Bold.ttf')

_MARGIN = 72
_HEADLINE_SIZE = 76
_LINE_H = 90
_MAX_LINES = 5
_FOOTER_PAD = 96
_ACCENT = (225, 35, 45)        # красный акцент-бар
_BRAND_COLOR = (255, 220, 70)  # жёлтый кикер


def _font(size):
    return ImageFont.truetype(_FONT_BOLD, size)


def extract_headline(text, max_chars=STORY_HEADLINE_MAX_CHARS):
    """Первая фраза поста, обрезанная по границе слова до max_chars.

    Хэштеги дописываются в КОНЕЦ готового поста, поэтому «первая фраза» их
    естественно отбрасывает. Возвращает '' если брать нечего.
    """
    if not text:
        return ''
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), '')
    if not first_line:
        return ''
    # Режем по первому терминатору предложения, но только если он не в самом
    # начале — иначе «S.L. Benfica…» обрежется на «S.».
    match = re.search(r'[.!?…](\s|$)', first_line)
    sentence = first_line[:match.start() + 1].strip() if match and match.start() >= 20 else first_line
    if len(sentence) <= max_chars:
        return sentence
    clipped = sentence[:max_chars].rsplit(' ', 1)[0].rstrip(' ,;:.—-')
    return (clipped or sentence[:max_chars].rstrip()) + '…'


def _cover(img, w, h):
    """Масштаб + центр-кроп, чтобы изображение полностью закрыло w×h."""
    scale = max(w / img.width, h / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.Resampling.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _contain(img, w, h):
    """Масштаб, чтобы изображение целиком влезло в w×h (без кропа)."""
    scale = min(w / img.width, h / img.height)
    return img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                      Image.Resampling.LANCZOS)


def _bottom_gradient(w, h, start_frac=0.45, max_alpha=235, power=1.35):
    """Маска: прозрачно сверху -> почти чёрно снизу, чтобы текст читался на любом фото."""
    column = Image.new('L', (1, h), 0)
    start = int(h * start_frac)
    span = h - start
    for y in range(start, h):
        column.putpixel((0, y), int(max_alpha * ((y - start) / span) ** power))
    return column.resize((w, h))


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ''
    for word in words:
        trial = (cur + ' ' + word).strip()
        if not cur or draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > _MAX_LINES:
        lines = lines[:_MAX_LINES]
        lines[-1] = lines[-1].rstrip() + '…'
    return lines


def render_headline_story(src_path, headline, out_path=None, brand=STORY_OVERLAY_BRAND):
    """Собрать сторис-картинку 9:16 с прожжённым заголовком. Возвращает путь к
    новому файлу или None при любой ошибке (тогда вызывающий грузит оригинал)."""
    try:
        with Image.open(src_path) as raw:
            src = raw.convert('RGB')

        # Фон: фото на весь кадр, размытое и затемнённое (закрывает леттербокс-поля).
        canvas = _cover(src, STORY_W, STORY_H).filter(ImageFilter.GaussianBlur(28))
        canvas = Image.blend(canvas, Image.new('RGB', canvas.size, (0, 0, 0)), 0.45)
        # Передний план: фото целиком, по центру.
        fg = _contain(src, STORY_W, STORY_H)
        canvas.paste(fg, ((STORY_W - fg.width) // 2, (STORY_H - fg.height) // 2))
        # Затемняющий градиент снизу под текст.
        canvas = Image.composite(
            Image.new('RGB', canvas.size, (0, 0, 0)), canvas, _bottom_gradient(STORY_W, STORY_H))

        draw = ImageDraw.Draw(canvas)
        head_font = _font(_HEADLINE_SIZE)
        lines = _wrap(draw, headline, head_font, STORY_W - 2 * _MARGIN)

        brand_font = _font(40) if brand else None
        kicker_h = 62 if brand else 0
        bar_h = 38
        block_h = bar_h + kicker_h + _LINE_H * len(lines)
        y = STORY_H - _FOOTER_PAD - block_h

        draw.rectangle([_MARGIN, y, _MARGIN + 96, y + 12], fill=_ACCENT)
        y += bar_h
        if brand:
            draw.text((_MARGIN, y), brand.upper(), font=brand_font, fill=_BRAND_COLOR)
            y += kicker_h
        for line in lines:
            draw.text((_MARGIN + 3, y + 3), line, font=head_font, fill=(0, 0, 0))  # тень
            draw.text((_MARGIN, y), line, font=head_font, fill=(255, 255, 255))
            y += _LINE_H

        if out_path is None:
            out_path = os.path.splitext(src_path)[0] + '.story.jpg'
        canvas.save(out_path, format='JPEG', quality=88)
        return out_path
    except Exception as e:
        logger.warning(f"[story-overlay] render failed for {src_path}: {e}")
        return None


def build_story_image(src_path, message):
    """Сторис-картинка с заголовком из поста. None => грузить оригинал без текста."""
    if not STORY_TEXT_OVERLAY_ENABLED:
        return None
    if not src_path or not os.path.isfile(src_path):
        return None
    headline = extract_headline(message)
    if not headline:
        return None
    return render_headline_story(src_path, headline)


def discard_overlay(path):
    """Best-effort уборка временного оверлей-файла."""
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass
