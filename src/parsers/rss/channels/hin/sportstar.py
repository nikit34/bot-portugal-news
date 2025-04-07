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

    description = re.sub(r'<[^>]+>', '', description)
    
    message = f"{title}\n\n{description}"
    
    image = ''
    if 'media_content' in entry:
        for media in entry['media_content']:
            if media.get('medium') == 'image':
                image = media.get('url', '')
                break
    
    return message, image
