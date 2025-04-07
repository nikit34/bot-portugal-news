import re
import logging
from typing import Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def is_valid_sportstar_entry(entry: Dict[str, Any]) -> bool:
    required_keys = ('title', 'description', 'media_content')
    has_required = all(entry.get(key) for key in required_keys)
    has_content = bool(entry.get('media_content') and entry.get('media_content')[0].get('url'))
        
    logger.debug(f"Sportstar entry check - has_required: {has_required}, has_content: {has_content}")
    return has_required or has_content


def parse_sportstar_entry(entry: Dict[str, Any]) -> Tuple[str, str]:
    logger.debug("Parsing Sportstar entry")
    title = entry.get('title')
    description = entry.get('description')

    description = re.sub(r'<[^>]+>', '', description).strip()
    message = f"{title}\n\n{description}"

    image = ''

    media_content = entry.get('media_content', [])
    for media in media_content:
        if media.get('medium') in ('image', 'video'):
            image = media.get('url', '')
            if image:
                break

    if not image and 'media_thumbnail' in entry:
        thumbnails = entry['media_thumbnail']
        if isinstance(thumbnails, list) and thumbnails:
            image = thumbnails[0].get('url', '')

    if not image and 'links' in entry:
        for link in entry['links']:
            if link.get('rel') == 'enclosure' and link.get('type', '').startswith('image/'):
                image = link.get('href', '')
                break

    return message, image