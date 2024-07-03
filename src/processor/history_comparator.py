import difflib

from src.static.settings import MESSAGE_SIMILARITY_THRESHOLD


def is_duplicate_message(head, posted_q):
    for post in posted_q:
        similarity = difflib.SequenceMatcher(None, head, post).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False
