import re
import html
import logging

logger = logging.getLogger('app')


def _first_img(summary_html):
    match = re.search(r'<img[^>]+src="([^"]+)"', summary_html)
    return html.unescape(match.group(1)) if match else ''


def _image(entry):
    # Most ge.globo items expose media:content; the live "Ao vivo" match pages carry
    # neither media nor an inline image and are intentionally dropped by is_valid.
    media_content = entry.get('media_content', [])
    if media_content and media_content[0].get('url'):
        return media_content[0]['url']
    return _first_img(entry.get('summary', ''))


def is_valid_ge_globo_entry(entry):
    has_text = bool(entry.get('title'))
    has_media = bool(_image(entry))

    logger.debug(f"ge.globo entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_ge_globo(entry):
    logger.debug("Parsing ge.globo entry")
    title = entry.get('title', '')
    raw_summary = entry.get('summary', '')

    image = _image(entry)
    summary = ' '.join(re.sub(r'<[^>]+>', '', raw_summary).split())

    message = title + ('\n' if title and summary else '') + summary
    logger.debug(f"Found ge.globo image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in ge.globo entry")

    return message, image
