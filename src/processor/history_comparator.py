import re
import difflib
from collections import deque

from src.static.settings import MESSAGE_SIMILARITY_THRESHOLD, KEY_SEARCH_LENGTH_CHARS
from src.static.ignore_list import IGNORE_POSTS
from src.static.sources import Platform


_URL_PATTERN = re.compile(r'http[s]?://\S+')
_WHITESPACE_PATTERN = re.compile(r'\s+')

# Платформы, в которые реально публикуем (Platform.ALL — служебная, не цель).
_PUBLISH_PLATFORMS = (Platform.FACEBOOK, Platform.INSTAGRAM, Platform.TELEGRAM)


def make_head(text):
    # Canonical dedup key. MUST be computed identically at publish time and when
    # reading FB/TG/IG history back — otherwise the same post yields a different key
    # per platform and the post gets republished to the "missing" platform every
    # run. Strip URLs and collapse all whitespace (incl. newlines) before cropping
    # so a leading title/newline or link can't shift the prefix.
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


def _find_posted(head, posted):
    # Single fuzzy pass over the dedup history. Returns the matching entry
    # [head, platforms] or None. seq1 is set once and reused across candidates
    # (difflib caches seq2's autojunk), so this stays O(history) per call — the
    # same cost the old three-bucket lookup had, now covering Instagram too.
    matcher = difflib.SequenceMatcher()
    matcher.set_seq1(head)
    for entry in posted:
        matcher.set_seq2(entry[0])
        if (matcher.real_quick_ratio() >= MESSAGE_SIMILARITY_THRESHOLD
                and matcher.quick_ratio() >= MESSAGE_SIMILARITY_THRESHOLD
                and matcher.ratio() >= MESSAGE_SIMILARITY_THRESHOLD):
            return entry
    return None


def get_decisions_publish_platforms(head, posted, platforms):
    # One lookup decides every platform: publish to a platform iff it's enabled
    # AND the post isn't already there. Instagram is a first-class platform here —
    # no more FB/TG-only branches that left IG ambiguous and caused reposts.
    entry = _find_posted(head, posted)
    already = entry[1] if entry is not None else ()
    return {
        platform: bool(platforms.get(platform)) and platform not in already
        for platform in _PUBLISH_PLATFORMS
    }


def is_duplicate_publish(decisions_publish_platforms):
    return not any(decisions_publish_platforms.get(p) for p in _PUBLISH_PLATFORMS)


def mark_posted(posted, head, succeeded):
    # Record that `head` now lives on `succeeded` platforms. If it already had an
    # entry (was on some platforms), extend it in place; otherwise add a new one.
    # A platform that failed this run keeps its decision True next run and retries,
    # without re-posting the platforms that already succeeded.
    if not succeeded:
        return
    entry = _find_posted(head, posted)
    if entry is not None:
        entry[1].update(succeeded)
    else:
        posted.appendleft([head, set(succeeded)])


def process_post_histories(facebook_history, telegram_history, instagram_history=None):
    # Merge per-platform histories into one `head -> {platforms}` structure. The
    # same story is published to FB/IG/TG with the same normalized head, so the IG
    # history mostly merges into existing FB/TG entries by exact head — the
    # structure stays ~the size of FB∪TG and the fuzzy-scan cost doesn't grow.
    instagram_history = instagram_history or []
    platforms_by_head = {}
    for source, platform in (
        (facebook_history, Platform.FACEBOOK),
        (telegram_history, Platform.TELEGRAM),
        (instagram_history, Platform.INSTAGRAM),
    ):
        for head in source:
            platforms_by_head.setdefault(head, set()).add(platform)

    # Rebuilt fresh each run from already length-capped histories, then grows by at
    # most MAX_POSTS_PER_RUN via mark_posted — so an unbounded deque stays small.
    posted = deque()
    for head, platforms in platforms_by_head.items():
        posted.append([head, platforms])
    return posted
