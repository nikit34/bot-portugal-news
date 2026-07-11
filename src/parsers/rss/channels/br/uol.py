import re
import html
import logging

logger = logging.getLogger('app')


def _first_img(summary_html):
    # UOL has no media tags; each item opens its description with an inline <img>.
    match = re.search(r'<img[^>]+src="([^"]+)"', summary_html)
    if not match:
        return ''
    src = html.unescape(match.group(1))
    # That inline thumbnail is only 142x100 (below IMAGE_MIN_WIDTH=500, so the quality
    # filter would drop every item). imguol serves larger variants at the same path;
    # rewrite the size token to 900x506 (verified). URLs without it pass through.
    return re.sub(r'_v2_\d+x\d+', '_v2_900x506', src)


def is_valid_uol_entry(entry):
    has_text = bool(entry.get('title'))
    has_media = bool(_first_img(entry.get('summary', '')))

    logger.debug(f"UOL entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_uol(entry):
    logger.debug("Parsing UOL entry")
    title = entry.get('title', '')
    raw_summary = entry.get('summary', '')

    image = _first_img(raw_summary)
    summary = ' '.join(re.sub(r'<[^>]+>', '', raw_summary).split())

    message = title + ('\n' if title and summary else '') + summary
    logger.debug(f"Found UOL image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in UOL entry")

    return message, image
