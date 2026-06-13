import re
import logging

logger = logging.getLogger('app')


def is_valid_zerozero_entry(entry):
    has_text = bool(entry.get('title'))
    has_media = bool(entry.get('media_content') and entry.get('media_content')[0].get('url'))

    logger.debug(f"Zerozero entry check - has_text: {has_text}, has_media: {has_media}")
    return has_text and has_media


def parse_zerozero_pt(entry):
    logger.debug("Parsing Zerozero entry")
    title = entry.get('title', '')
    raw_summary = entry.get('summary', '')
    summary = re.sub(r'<[^>]+>', '', raw_summary).strip()

    message = title + ('\n' if title and summary else '') + summary

    media_content = entry.get('media_content', [])
    image = media_content[0].get('url') if media_content else ''
    logger.debug(f"Found Zerozero image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in Zerozero entry")

    return message, image
