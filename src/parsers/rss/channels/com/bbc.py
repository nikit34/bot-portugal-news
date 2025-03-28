import re
import logging

logger = logging.getLogger(__name__)


def check_bbc_com(entry):
    required_keys = ('summary', 'title', 'media_thumbnail')
    has_required = all(entry.get(key) for key in required_keys)
    has_thumbnail = bool(entry.get('media_thumbnail') and entry.get('media_thumbnail')[0].get('url'))
    
    logger.debug(f"BBC entry check - has_required: {has_required}, has_thumbnail: {has_thumbnail}")
    return not (has_required or has_thumbnail)


def parse_bbc_com(entry):
    logger.debug("Parsing BBC entry")
    summary = entry.get('summary')
    title = entry.get('title')
    
    if not summary or not title:
        logger.warning("BBC entry missing summary or title")
        return '', ''

    message = title + '\n' + summary
    media_thumbnail = entry.get('media_thumbnail', [])
    image = media_thumbnail[0].get('url') if media_thumbnail else ''
    
    if image:
        logger.debug(f"Found BBC image URL: {image}")
        image = re.sub(r"/\d+/cpsprodpb", '/960/cpsprodpb', image)
        logger.debug(f"Modified BBC image URL: {image}")
    else:
        logger.warning("No image found in BBC entry")

    return message, image
