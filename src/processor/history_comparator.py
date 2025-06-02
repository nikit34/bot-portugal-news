import difflib

from src.static.settings import MESSAGE_SIMILARITY_THRESHOLD
from src.static.ignore_list import IGNORE_POSTS


def _is_ignored_prefix(head):
    for ignored_prefix in IGNORE_POSTS:
        prefix_length = len(ignored_prefix)
        head_prefix = head[:prefix_length]
        similarity = difflib.SequenceMatcher(None, head_prefix, ignored_prefix).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False


def is_duplicate_message(head, posted_q):
    for post in posted_q:
        similarity = difflib.SequenceMatcher(None, head, post).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False
