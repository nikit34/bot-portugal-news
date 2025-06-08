from src.processor.history_comparator import _is_duplicate_message, is_ignored_prefix, get_decisions_publish_platforms, is_duplicate_publish, process_post_histories
from src.static.ignore_list import IGNORE_POSTS
from src.static.sources import Platform
from collections import deque

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

def test_is_duplicate_publish_all_false():
    decisions_publish_platforms = {
        Platform.FACEBOOK: False,
        Platform.TELEGRAM: False,
        Platform.INSTAGRAM: False
    }
    
    assert is_duplicate_publish(decisions_publish_platforms)

def test_is_duplicate_publish_some_true():
    decisions_publish_platforms = {
        Platform.FACEBOOK: True,
        Platform.TELEGRAM: False,
        Platform.INSTAGRAM: False
    }
    
    assert not is_duplicate_publish(decisions_publish_platforms)

def test_is_duplicate_publish_all_true():
    decisions_publish_platforms = {
        Platform.FACEBOOK: True,
        Platform.TELEGRAM: True,
        Platform.INSTAGRAM: True
    }
    
    assert not is_duplicate_publish(decisions_publish_platforms)

def test_process_post_histories_empty():
    facebook_history = []
    telegram_history = []
    
    result = process_post_histories(facebook_history, telegram_history)
    
    assert isinstance(result[Platform.ALL], deque)
    assert isinstance(result[Platform.TELEGRAM], deque)
    assert isinstance(result[Platform.FACEBOOK], deque)
    assert len(result[Platform.ALL]) == 0
    assert len(result[Platform.TELEGRAM]) == 0
    assert len(result[Platform.FACEBOOK]) == 0

def test_process_post_histories_with_duplicates():
    facebook_history = ["post1", "post2", "post3"]
    telegram_history = ["post2", "post3", "post4"]
    
    result = process_post_histories(facebook_history, telegram_history)
    
    assert isinstance(result[Platform.ALL], deque)
    assert isinstance(result[Platform.TELEGRAM], deque)
    assert isinstance(result[Platform.FACEBOOK], deque)
    
    assert len(result[Platform.ALL]) == 2
    assert "post2" in result[Platform.ALL]
    assert "post3" in result[Platform.ALL]
    
    assert len(result[Platform.TELEGRAM]) == 1
    assert "post4" in result[Platform.TELEGRAM]
    
    assert len(result[Platform.FACEBOOK]) == 1
    assert "post1" in result[Platform.FACEBOOK]

def test_process_post_histories_no_duplicates():
    facebook_history = ["post1", "post2"]
    telegram_history = ["post3", "post4"]
    
    result = process_post_histories(facebook_history, telegram_history)
    
    assert isinstance(result[Platform.ALL], deque)
    assert isinstance(result[Platform.TELEGRAM], deque)
    assert isinstance(result[Platform.FACEBOOK], deque)
    
    assert len(result[Platform.ALL]) == 0
    
    assert len(result[Platform.TELEGRAM]) == 2
    assert "post3" in result[Platform.TELEGRAM]
    assert "post4" in result[Platform.TELEGRAM]
    
    assert len(result[Platform.FACEBOOK]) == 2
    assert "post1" in result[Platform.FACEBOOK]
    assert "post2" in result[Platform.FACEBOOK] 