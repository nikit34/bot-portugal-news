import re
import logging

logger = logging.getLogger('app')


def is_valid_trivela_entry(entry):
    has_text = any(entry.get(key) for key in ('title', 'summary'))
    has_media = bool(entry.get('media_content') and entry.get('media_content')[0].get('url'))

    logger.debug(f"Trivela entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_trivela(entry):
    logger.debug("Parsing Trivela entry")
    title = entry.get('title', '')
    raw_summary = entry.get('summary', '')
    summary = ' '.join(re.sub(r'<[^>]+>', '', raw_summary).split())

    message = title + ('\n' if title and summary else '') + summary

    media_content = entry.get('media_content', [])
    image = media_content[0].get('url') if media_content else ''
    logger.debug(f"Found Trivela image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in Trivela entry")

    return message, image
