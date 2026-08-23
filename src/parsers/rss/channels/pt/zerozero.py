import re
import html
import logging

logger = logging.getLogger('app')

_ENTITY_LINK = re.compile(r'\{[A-Z_]+\|\d+\|([^}]*)\}')
_TAG = re.compile(r'<[^>]+>')
_SPACES = re.compile(r'[ \t]{2,}')


def _clean(text):
    text = _ENTITY_LINK.sub(r'\1', text or '')
    text = _TAG.sub('', text)
    text = html.unescape(text).replace('\xa0', ' ')
    return _SPACES.sub(' ', text).strip()


def is_valid_zerozero_entry(entry):
    has_text = bool(entry.get('title'))
    has_media = bool(entry.get('media_content') and entry.get('media_content')[0].get('url'))

    logger.debug(f"Zerozero entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_zerozero_pt(entry):
    logger.debug("Parsing Zerozero entry")
    title = _clean(entry.get('title', ''))
    summary = _clean(entry.get('summary', ''))

    message = title + ('\n' if title and summary else '') + summary

    media_content = entry.get('media_content', [])
    image = media_content[0].get('url') if media_content else ''
    logger.debug(f"Found Zerozero image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in Zerozero entry")

    return message, image
