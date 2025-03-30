import difflib
import logging
from typing import List

from src.static.settings import MESSAGE_SIMILARITY_THRESHOLD
from src.storage.redis_client import PostHistoryStorage

logger = logging.getLogger(__name__)

def is_duplicate_message(head: str, storage: PostHistoryStorage) -> bool:
    recent_posts = storage.get_recent_posts()
    
    for post in recent_posts:
        similarity = difflib.SequenceMatcher(None, head, post).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            logger.info(f"Found duplicate post with similarity {similarity:.2f}")
            return True
    return False
