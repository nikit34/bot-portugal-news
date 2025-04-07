import re
import logging

logger = logging.getLogger(__name__)


def is_valid_bbc_com_entry(entry):
    required_keys = ('summary', 'title', 'media_thumbnail')
    has_text = all(entry.get(key) for key in required_keys)
    has_media = bool(entry.get('media_thumbnail') and entry.get('media_thumbnail')[0].get('url'))
    
    logger.debug(f"BBC entry check - has_text: {has_text}, has_media: {has_media}")
    return (has_text or has_media)


def parse_bbc_com(entry):
    logger.debug("Parsing BBC entry")
    summary = entry.get('summary')
    title = entry.get('title')

    message = title + '\n' + summary
    media_thumbnail = entry.get('media_thumbnail')
    image = media_thumbnail[0].get('url')
    
    logger.debug(f"Found BBC image URL: {image}")
    image = re.sub(r"/\d+/cpsprodpb", '/960/cpsprodpb', image)
    logger.debug(f"Modified BBC image URL: {image}")

    return message, image
