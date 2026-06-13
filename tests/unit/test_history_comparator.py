from collections import deque

from src.processor.history_comparator import (
    _find_posted,
    is_ignored_prefix,
    get_decisions_publish_platforms,
    is_duplicate_publish,
    process_post_histories,
    mark_posted,
    make_head,
)
from src.static.ignore_list import IGNORE_POSTS
from src.static.sources import Platform


ALL_ON = {Platform.FACEBOOK: True, Platform.INSTAGRAM: True, Platform.TELEGRAM: True}


def test_make_head_collapses_newlines_and_strips_urls():
    raw = "Benfica vence o Porto\nVeja em https://abola.pt/x apos jogo intenso"
    head = make_head(raw)
    assert "\n" not in head
    assert "http" not in head
    assert head == "Benfica vence o Porto Veja em apos jogo intenso"


def test_is_ignored_prefix():
    IGNORE_POSTS.append("Breaking news:")
    assert is_ignored_prefix("Breaking news: Something happened")
    assert is_ignored_prefix("Breaking newz: Something happened")
    assert is_ignored_prefix("Breaking news! Something happened")
    assert not is_ignored_prefix("Regular news: Something happened")
    assert not is_ignored_prefix("Today's breaking news: Something happened")


# --- _find_posted (matching primitive) ---

def test_find_posted_exact_match_returns_entry():
    posted = deque([['Test message', {Platform.FACEBOOK}]])
    entry = _find_posted('Test message', posted)
    assert entry is not None and entry[1] == {Platform.FACEBOOK}


def test_find_posted_fuzzy_match():
    posted = deque([['Original test message', {Platform.TELEGRAM}]])
    assert _find_posted('Original test massage', posted) is not None


def test_find_posted_no_match():
    posted = deque([['Original test message', {Platform.TELEGRAM}]])
    assert _find_posted('Completely different text', posted) is None


def test_find_posted_empty_history():
    assert _find_posted('Test message', deque()) is None


# --- process_post_histories (merge into head -> platforms) ---

def test_process_post_histories_empty():
    posted = process_post_histories([], [])
    assert isinstance(posted, deque)
    assert len(posted) == 0


def test_process_post_histories_merges_platforms_by_head():
    posted = process_post_histories(['a', 'b'], ['b', 'c'], ['b', 'd'])
    by_head = {head: platforms for head, platforms in posted}

    assert by_head['a'] == {Platform.FACEBOOK}
    assert by_head['b'] == {Platform.FACEBOOK, Platform.TELEGRAM, Platform.INSTAGRAM}
    assert by_head['c'] == {Platform.TELEGRAM}
    assert by_head['d'] == {Platform.INSTAGRAM}
    assert len(posted) == 4  # 'b' is one merged entry, not three


def test_process_post_histories_instagram_optional():
    posted = process_post_histories(['a'], ['a'])  # IG omitted
    by_head = {head: platforms for head, platforms in posted}
    assert by_head['a'] == {Platform.FACEBOOK, Platform.TELEGRAM}


# --- get_decisions_publish_platforms ---

def test_decisions_fresh_post_publishes_everywhere():
    decision = get_decisions_publish_platforms('new', deque(), ALL_ON)
    assert decision[Platform.FACEBOOK]
    assert decision[Platform.INSTAGRAM]
    assert decision[Platform.TELEGRAM]
    assert not is_duplicate_publish(decision)


def test_decisions_already_on_all_is_duplicate():
    posted = deque([['x', {Platform.FACEBOOK, Platform.INSTAGRAM, Platform.TELEGRAM}]])
    decision = get_decisions_publish_platforms('x', posted, ALL_ON)
    assert not any(decision.values())
    assert is_duplicate_publish(decision)


def test_decisions_backfills_only_missing_instagram():
    # On FB+TG already; IG enabled but missing => publish to IG only.
    posted = deque([['x', {Platform.FACEBOOK, Platform.TELEGRAM}]])
    decision = get_decisions_publish_platforms('x', posted, ALL_ON)
    assert decision[Platform.INSTAGRAM] is True
    assert decision[Platform.FACEBOOK] is False
    assert decision[Platform.TELEGRAM] is False
    assert not is_duplicate_publish(decision)


def test_decisions_respect_disabled_platform():
    platforms = {Platform.FACEBOOK: False, Platform.INSTAGRAM: True, Platform.TELEGRAM: True}
    decision = get_decisions_publish_platforms('new', deque(), platforms)
    assert decision[Platform.FACEBOOK] is False
    assert decision[Platform.INSTAGRAM] is True
    assert decision[Platform.TELEGRAM] is True


# --- mark_posted ---

def test_mark_posted_new_head_creates_entry():
    posted = deque()
    mark_posted(posted, 'x', {Platform.FACEBOOK, Platform.INSTAGRAM, Platform.TELEGRAM})
    assert _find_posted('x', posted)[1] == {Platform.FACEBOOK, Platform.INSTAGRAM, Platform.TELEGRAM}


def test_mark_posted_extends_existing_entry_without_duplicating():
    posted = deque([['x', {Platform.TELEGRAM}]])
    mark_posted(posted, 'x', {Platform.FACEBOOK})
    assert _find_posted('x', posted)[1] == {Platform.FACEBOOK, Platform.TELEGRAM}
    assert len(posted) == 1


def test_mark_posted_ignores_empty_success():
    posted = deque()
    mark_posted(posted, 'x', set())
    assert len(posted) == 0


def test_instagram_not_reposted_after_facebook_failure():
    # Regression for the IG-dedup gap: FB failed but IG+TG succeeded this run.
    # Next run must request only FB (the platform that failed), NOT re-post to IG.
    posted = process_post_histories([], [], [])
    mark_posted(posted, 'story', {Platform.INSTAGRAM, Platform.TELEGRAM})

    decision = get_decisions_publish_platforms('story', posted, ALL_ON)
    assert decision[Platform.FACEBOOK] is True
    assert decision[Platform.INSTAGRAM] is False
    assert decision[Platform.TELEGRAM] is False


# --- is_duplicate_publish ---

def test_is_duplicate_publish_all_false():
    assert is_duplicate_publish(
        {Platform.FACEBOOK: False, Platform.TELEGRAM: False, Platform.INSTAGRAM: False})


def test_is_duplicate_publish_some_true():
    assert not is_duplicate_publish(
        {Platform.FACEBOOK: True, Platform.TELEGRAM: False, Platform.INSTAGRAM: False})


def test_is_duplicate_publish_all_true():
    assert not is_duplicate_publish(
        {Platform.FACEBOOK: True, Platform.TELEGRAM: True, Platform.INSTAGRAM: True})
