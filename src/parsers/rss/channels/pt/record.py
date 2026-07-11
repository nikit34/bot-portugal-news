import re
import logging

logger = logging.getLogger('app')


def _strip_cdata(text):
    # Record double-encodes its <title> as "<![CDATA[ ... ]]>" inside the element text,
    # so feedparser hands back the literal wrapper instead of unwrapping it.
    match = re.match(r'^\s*<!\[CDATA\[(.*?)\]\]>\s*$', text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _enclosure_image(entry):
    enclosures = entry.get('enclosures', [])
    href = enclosures[0].get('href', '') if enclosures else ''
    # Record's enclosure defaults to a 220x220 thumbnail (below IMAGE_MIN_WIDTH=500, so the
    # quality filter would drop every item). The CDN serves a larger 800x533 variant at the
    # same path — 640x420/1200x630 return error stubs, so 800x533 is the only good upsize.
    # Rewrite the size token; URLs without it (e.g. tests, other hosts) pass through.
    return re.sub(r'img_\d+x\d+uu', 'img_800x533uu', href)


def is_valid_record_entry(entry):
    has_text = any(entry.get(key) for key in ('title', 'summary'))
    has_media = bool(_enclosure_image(entry))

    logger.debug(f"Record entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_record_pt(entry):
    logger.debug("Parsing Record entry")
    title = _strip_cdata(entry.get('title', ''))
    summary = _strip_cdata(entry.get('summary', ''))

    message = title + ('\n' if title and summary else '') + summary
    image = _enclosure_image(entry)
    logger.debug(f"Found Record image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in Record entry")

    return message, image
