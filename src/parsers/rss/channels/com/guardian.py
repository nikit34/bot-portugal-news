import re
import html
import logging

logger = logging.getLogger('app')


def _largest_media_content(entry):
    # The Guardian feed carries 2-3 <media:content> variants per item (widths 140/460/700);
    # feedparser exposes them as entry['media_content']. Pick the widest. Its URL is signed
    # (?...&s=<hash>), so it must be used verbatim — rewriting the query string (as the BBC
    # parser does for its CDN) invalidates the signature and the host returns 401.
    media = entry.get('media_content') or []
    best_url = ''
    best_width = -1
    for item in media:
        url = item.get('url')
        if not url:
            continue
        try:
            width = int(item.get('width') or 0)
        except (TypeError, ValueError):
            width = 0
        if width > best_width:
            best_width = width
            best_url = url
    return best_url


def _clean_summary(raw_summary):
    # The Guardian <description> is HTML (a <p> with links). Strip tags, unescape entities
    # and collapse whitespace into a flat summary line.
    text = re.sub(r'<[^>]+>', '', raw_summary)
    return ' '.join(html.unescape(text).split())


def is_valid_guardian_entry(entry):
    has_text = bool(entry.get('title'))
    has_media = bool(_largest_media_content(entry))

    logger.debug(f"Guardian entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_guardian(entry):
    logger.debug("Parsing Guardian entry")
    title = entry.get('title', '')
    summary = _clean_summary(entry.get('summary', ''))

    message = title + ('\n' if title and summary else '') + summary
    image = _largest_media_content(entry)
    logger.debug(f"Found Guardian image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in Guardian entry")

    return message, image
