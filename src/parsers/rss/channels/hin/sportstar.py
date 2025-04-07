import re
import logging
from typing import Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def is_valid_sportstar_entry(entry: Dict[str, Any]) -> bool:
    """Check if Sportstar entry has all required fields"""
    required_keys = ('title', 'link', 'published', 'description')
    has_required = all(entry.get(key) for key in required_keys)
    
    if not has_required:
        logger.debug("Sportstar entry missing required keys")
        return False
        
    logger.debug(f"Sportstar entry check - has_required: {has_required}")
    return has_required


def parse_sportstar_entry(entry: Dict[str, Any]) -> Tuple[str, str]:
    """Parse Sportstar entry into message and image"""
    logger.debug("Parsing Sportstar entry")
    title = entry.get('title', '')
    description = entry.get('description', '')
    
    if not title or not description:
        logger.warning("Sportstar entry missing title or description")
        return '', ''

    # Удаляем HTML-теги из описания
    description = re.sub(r'<[^>]+>', '', description).strip()
    message = f"{title}\n\n{description}"

    # Попытка найти изображение
    image = ''

    # 1. media:content
    media_content = entry.get('media_content', [])
    for media in media_content:
        if media.get('medium') in ('image', 'video'):
            image = media.get('url', '')
            if image:
                break

    # 2. media:thumbnail
    if not image and 'media_thumbnail' in entry:
        thumbnails = entry['media_thumbnail']
        if isinstance(thumbnails, list) and thumbnails:
            image = thumbnails[0].get('url', '')

    # 3. enclosure (иногда бывает)
    if not image and 'links' in entry:
        for link in entry['links']:
            if link.get('rel') == 'enclosure' and link.get('type', '').startswith('image/'):
                image = link.get('href', '')
                break

    return message, image