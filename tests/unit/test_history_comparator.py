from src.processor.history_comparator import _is_duplicate_message, is_ignored_prefix, get_decisions_publish_platforms
from src.static.ignore_list import IGNORE_POSTS
from src.static.sources import Platform

def test_is_ignored_prefix():
    IGNORE_POSTS.append("Breaking news:")
    assert is_ignored_prefix("Breaking news: Something happened")
    
    assert is_ignored_prefix("Breaking newz: Something happened")
    assert is_ignored_prefix("Breaking news! Something happened")
    
    assert not is_ignored_prefix("Regular news: Something happened")
    
    assert not is_ignored_prefix("Today's breaking news: Something happened")

def test_is_duplicate_message_with_exact_match(posted_q):
    message = "Test message"
    posted_q.append(message)
    
    assert _is_duplicate_message(message, posted_q)

def test_is_duplicate_message_with_similar_message(posted_q):
    posted_q.append("Original test message")
    
    similar_message = "Original test massage"
    assert _is_duplicate_message(similar_message, posted_q)

def test_is_duplicate_message_with_different_message(posted_q):
    posted_q.append("Original test message")
    
    different_message = "Completely different text"
    assert not _is_duplicate_message(different_message, posted_q)

def test_is_duplicate_message_with_empty_queue(posted_q):
    message = "Test message"
    
    assert not _is_duplicate_message(message, posted_q)

def test_get_decisions_publish_platforms_all_duplicated():
    head = "Test message"
    posted_d = {
        Platform.ALL: ["Test message"],
        Platform.TELEGRAM: [],
        Platform.FACEBOOK: []
    }
    platforms = {
        Platform.FACEBOOK: True,
        Platform.TELEGRAM: True,
        Platform.INSTAGRAM: True
    }
    
    result = get_decisions_publish_platforms(head, posted_d, platforms)
    
    assert not result[Platform.FACEBOOK]
    assert not result[Platform.TELEGRAM]
    assert not result[Platform.INSTAGRAM]

def test_get_decisions_publish_platforms_telegram_duplicated():
    head = "Test message"
    posted_d = {
        Platform.ALL: [],
        Platform.TELEGRAM: ["Test message"],
        Platform.FACEBOOK: []
    }
    platforms = {
        Platform.FACEBOOK: False,
        Platform.TELEGRAM: True,
        Platform.INSTAGRAM: False
    }
    
    result = get_decisions_publish_platforms(head, posted_d, platforms)
    
    assert not result[Platform.FACEBOOK]
    assert not result[Platform.TELEGRAM]
    assert not result[Platform.INSTAGRAM]

def test_get_decisions_publish_platforms_facebook_duplicated():
    head = "Test message"
    posted_d = {
        Platform.ALL: [],
        Platform.TELEGRAM: [],
        Platform.FACEBOOK: ["Test message"]
    }
    platforms = {
        Platform.FACEBOOK: True,
        Platform.TELEGRAM: False,
        Platform.INSTAGRAM: True
    }
    
    result = get_decisions_publish_platforms(head, posted_d, platforms)
    
    assert not result[Platform.FACEBOOK]
    assert not result[Platform.TELEGRAM]
    assert not result[Platform.INSTAGRAM]

def test_get_decisions_publish_platforms_no_duplicates():
    head = "Test message"
    posted_d = {
        Platform.ALL: [],
        Platform.TELEGRAM: [],
        Platform.FACEBOOK: []
    }
    platforms = {
        Platform.FACEBOOK: True,
        Platform.TELEGRAM: True,
        Platform.INSTAGRAM: True
    }
    
    result = get_decisions_publish_platforms(head, posted_d, platforms)
    
    assert result[Platform.FACEBOOK]
    assert result[Platform.TELEGRAM]
    assert result[Platform.INSTAGRAM]

def test_get_decisions_publish_platforms_only_telegram():
    head = "Test message"
    posted_d = {
        Platform.ALL: [],
        Platform.TELEGRAM: [],
        Platform.FACEBOOK: ["Test message"]
    }
    platforms = {
        Platform.FACEBOOK: False,
        Platform.TELEGRAM: True,
        Platform.INSTAGRAM: False
    }
    
    result = get_decisions_publish_platforms(head, posted_d, platforms)
    
    assert not result[Platform.FACEBOOK]
    assert result[Platform.TELEGRAM]
    assert not result[Platform.INSTAGRAM]

def test_get_decisions_publish_platforms_only_instagram():
    head = "Test message"
    posted_d = {
        Platform.ALL: [],
        Platform.TELEGRAM: ["Test message"],
        Platform.FACEBOOK: []
    }
    platforms = {
        Platform.FACEBOOK: False,
        Platform.TELEGRAM: False,
        Platform.INSTAGRAM: True
    }
    
    result = get_decisions_publish_platforms(head, posted_d, platforms)
    
    assert not result[Platform.FACEBOOK]
    assert not result[Platform.TELEGRAM]
    assert result[Platform.INSTAGRAM] 