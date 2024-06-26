import difflib

from src.static.settings import MESSAGE_SIMILARITY_THRESHOLD, KEY_SEARCH_LENGTH_CHARS


def _compare_messages(message, posted_q):
    for post in posted_q:
        similarity = difflib.SequenceMatcher(None, message, post).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False


def is_duplicate_message(translated_message, posted_q):
    head = translated_message[:KEY_SEARCH_LENGTH_CHARS].strip()
    if _compare_messages(head, posted_q):
        return True
    posted_q.appendleft(head)
    return False
