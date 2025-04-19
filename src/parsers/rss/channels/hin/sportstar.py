import re
import logging
from typing import Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger('app')


def is_valid_sportstar_entry(entry: Dict[str, Any]) -> bool:
    required_keys = ('title', 'description')
    has_text = any(entry.get(key) for key in required_keys)
    has_media = bool(entry.get('media_content') and entry.get('media_content')[0].get('url'))
        
    logger.debug(f"Sportstar entry check - has_text: {has_text}, has_media: {has_media}")
    return (has_text and has_media)


def parse_sportstar_entry(entry: Dict[str, Any]) -> Tuple[str, str]:
    logger.debug("Parsing Sportstar entry")
    title = entry.get('title', '')
    raw_description = entry.get('description', '')
    description = re.sub(r'<[^>]+>', '', raw_description).strip()

    message = title + ('\n' if title and description else '') + description

    media_content = entry.get('media_content', [])
    image = media_content[0].get('url') if media_content else ''
    logger.debug(f"Found Sportstar image URL: {image}")

    if not image or not message:
        logger.error("No image or message found in Sportstar entry")

    return message, image