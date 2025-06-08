import difflib
from collections import deque

from src.static.settings import MESSAGE_SIMILARITY_THRESHOLD
from src.static.ignore_list import IGNORE_POSTS


def is_ignored_prefix(head):
    for ignored_prefix in IGNORE_POSTS:
        prefix_length = len(ignored_prefix)
        head_prefix = head[:prefix_length]
        similarity = difflib.SequenceMatcher(None, head_prefix, ignored_prefix).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False


def _is_duplicate_message(head, posted_l):
    for post in posted_l:
        similarity = difflib.SequenceMatcher(None, head, post).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False


def get_decisions_publish_platforms(head, posted_d, decisions_publish_platforms):
    duplicated_general = _is_duplicate_message(head, posted_d.get('general', []))
    duplicated_telegram = _is_duplicate_message(head, posted_d.get('telegram', []))
    duplicated_facebook = _is_duplicate_message(head, posted_d.get('facebook', []))

    if duplicated_general:
        decisions_publish_platforms['facebook'] = False
        decisions_publish_platforms['telegram'] = False
        decisions_publish_platforms['instagram'] = False
    elif duplicated_telegram:
        decisions_publish_platforms['facebook'] = True
        decisions_publish_platforms['instagram'] = True
        decisions_publish_platforms['telegram'] = False
    elif duplicated_facebook:
        decisions_publish_platforms['telegram'] = True
        decisions_publish_platforms['facebook'] = False
        decisions_publish_platforms['instagram'] = False
    else:
        pass

    return decisions_publish_platforms

def is_duplicate_publish(decisions_publish_platforms):
    return not any(decisions_publish_platforms.get(p) for p in ['facebook', 'telegram', 'instagram'])



def process_post_histories(facebook_history, telegram_history):
    fb_set = set(facebook_history)
    tg_set = set(telegram_history)

    general_posted_q = deque(fb_set & tg_set)
    telegram_posted_q = deque([post for post in telegram_history if post not in general_posted_q])
    facebook_posted_q = deque([post for post in facebook_history if post not in general_posted_q])

    return {
        'general': general_posted_q, 'telegram': telegram_posted_q, 'facebook': facebook_posted_q
    }