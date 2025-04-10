import re
import logging

logger = logging.getLogger(__name__)


def is_valid_bbc_com_entry(entry):
    required_keys = ('summary', 'title')
    has_text = any(entry.get(key) for key in required_keys)
    has_media = bool(entry.get('media_thumbnail') and entry.get('media_thumbnail')[0].get('url'))
    
    logger.debug(f"BBC entry check - has_text: {has_text}, has_media: {has_media}")
    return (has_text and has_media)


def parse_bbc_com(entry):
    logger.debug("Parsing BBC entry")
    summary = entry.get('summary', '')
    title = entry.get('title', '')

    message = title + ('\n' if title and summary else '') + summary
    media_thumbnail = entry.get('media_thumbnail', [])
    image = media_thumbnail[0].get('url') if media_thumbnail else ''
    
    logger.debug(f"Found BBC image URL: {image}")
    image = re.sub(r"/\d+/cpsprodpb", '/960/cpsprodpb', image)
    logger.debug(f"Modified BBC image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in BBC entry")

    return message, image
