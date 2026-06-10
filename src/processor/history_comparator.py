import re
import difflib
from collections import deque

from src.static.settings import MESSAGE_SIMILARITY_THRESHOLD, COUNT_UNIQUE_MESSAGES, KEY_SEARCH_LENGTH_CHARS
from src.static.ignore_list import IGNORE_POSTS
from src.static.sources import Platform


_URL_PATTERN = re.compile(r'http[s]?://\S+')
_WHITESPACE_PATTERN = re.compile(r'\s+')


def make_head(text):
    # Canonical dedup key. MUST be computed identically at publish time and when
    # reading FB/TG history back — otherwise the same post yields a different key
    # per platform and process_post_histories' exact-match `fb_set & tg_set`
    # never puts it in Platform.ALL, so it gets republished to the "missing"
    # platform on every run. Strip URLs and collapse all whitespace (incl.
    # newlines) before cropping so a leading title/newline or link can't shift
    # the prefix.
    if not text:
        return ''
    text = _URL_PATTERN.sub('', text)
    text = _WHITESPACE_PATTERN.sub(' ', text).strip()
    return text[:KEY_SEARCH_LENGTH_CHARS].strip()


def is_ignored_prefix(head):
    for ignored_prefix in IGNORE_POSTS:
        prefix_length = len(ignored_prefix)
        head_prefix = head[:prefix_length]
        similarity = difflib.SequenceMatcher(None, head_prefix, ignored_prefix).ratio()
        if similarity >= MESSAGE_SIMILARITY_THRESHOLD:
            return True
    return False


def _is_duplicate_message(head, posted_l):
    matcher = difflib.SequenceMatcher()
    matcher.set_seq1(head)
    for post in posted_l:
        matcher.set_seq2(post)
        if (matcher.real_quick_ratio() >= MESSAGE_SIMILARITY_THRESHOLD
                and matcher.quick_ratio() >= MESSAGE_SIMILARITY_THRESHOLD
                and matcher.ratio() >= MESSAGE_SIMILARITY_THRESHOLD):
            return True
    return False


def get_decisions_publish_platforms(head, posted_d, platforms):
    decisions_publish_platforms = {
        Platform.FACEBOOK: False,
        Platform.INSTAGRAM: False,
        Platform.TELEGRAM: False,
    }

    if _is_duplicate_message(head, posted_d.get(Platform.ALL, [])):
        return decisions_publish_platforms

    if _is_duplicate_message(head, posted_d.get(Platform.TELEGRAM, [])):
        decisions_publish_platforms[Platform.FACEBOOK] = platforms[Platform.FACEBOOK]
        decisions_publish_platforms[Platform.INSTAGRAM] = platforms[Platform.INSTAGRAM]
        return decisions_publish_platforms

    if _is_duplicate_message(head, posted_d.get(Platform.FACEBOOK, [])):
        decisions_publish_platforms[Platform.TELEGRAM] = platforms[Platform.TELEGRAM]
        return decisions_publish_platforms

    return platforms


def is_duplicate_publish(decisions_publish_platforms):
    return not any(decisions_publish_platforms.get(p) for p in [Platform.FACEBOOK, Platform.TELEGRAM, Platform.INSTAGRAM])


def process_post_histories(facebook_history, telegram_history, maxlen=COUNT_UNIQUE_MESSAGES):
    fb_set = set(facebook_history)
    tg_set = set(telegram_history)
    general_set = fb_set & tg_set

    general_posted_q = deque(general_set, maxlen=maxlen)
    telegram_posted_q = deque((post for post in telegram_history if post not in general_set), maxlen=maxlen)
    facebook_posted_q = deque((post for post in facebook_history if post not in general_set), maxlen=maxlen)

    return {
        Platform.ALL: general_posted_q,
        Platform.TELEGRAM: telegram_posted_q,
        Platform.FACEBOOK: facebook_posted_q
    }