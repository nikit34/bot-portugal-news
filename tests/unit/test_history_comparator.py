from src.processor.history_comparator import _is_duplicate_message, is_ignored_prefix
from src.static.ignore_list import IGNORE_POSTS

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