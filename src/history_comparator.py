import difflib

from src.static.settings import THRESHOLD


def compare_messages(message, posted_q):
    for post in posted_q:
        similarity = difflib.SequenceMatcher(None, message, post).ratio()
        if similarity >= THRESHOLD:
            return True
    return False
