import re
import logging

logger = logging.getLogger('app')

# Дефолтный парсер для источников БЕЗ выделенного хендлера (напр. food-фиды на
# WordPress). Тянем заголовок + очищенное описание и первую картинку из
# media:content / media:thumbnail / enclosure / <img> в content:encoded|summary.
_TAG_RE = re.compile(r'<[^>]+>')
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_CDATA_RE = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)
_IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.gif')


def _strip_html(text):
    if not text:
        return ''
    text = _CDATA_RE.sub(r'\1', text)
    text = _TAG_RE.sub(' ', text)
    text = (text.replace('&nbsp;', ' ').replace('&amp;', '&')
                .replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'").replace('&quot;', '"'))
    text = re.sub(r'&#\d+;', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _looks_like_image(url):
    u = (url or '').lower().split('?')[0]
    return u.endswith(_IMG_EXT) or 'image' in u


def _first_image(entry):
    for key in ('media_content', 'media_thumbnail'):
        for media in entry.get(key, []) or []:
            url = media.get('url')
            if url and _looks_like_image(url):
                return url
    for enc in entry.get('enclosures', []) or []:
        href = enc.get('href', '')
        if href and ((enc.get('type', '') or '').startswith('image') or _looks_like_image(href)):
            return href
    html = ''
    content = entry.get('content')
    if content:
        html = content[0].get('value', '') if isinstance(content, list) else str(content)
    html = html or entry.get('summary', '') or ''
    match = _IMG_RE.search(html)
    return match.group(1) if match else ''


def is_valid_generic_entry(entry):
    # Нужны и текст (заголовок), и картинка — иначе постить нечего/не из чего собрать
    # плашку/reel.
    return bool(entry.get('title')) and bool(_first_image(entry))


def parse_generic(entry):
    title = _strip_html(entry.get('title', ''))
    summary = _strip_html(entry.get('summary', ''))
    message = title
    if summary and summary.lower() != title.lower():
        message = title + '\n' + summary[:400]      # короткий хвост под озвучку/подпись
    image = _first_image(entry)
    if not image or not message:
        logger.debug("[RSS] generic entry missing image or text")
    return message, image
