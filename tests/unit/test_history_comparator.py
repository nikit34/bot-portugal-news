from src.processor.history_comparator import is_duplicate_message, _is_ignored_prefix
from src.static.ignore_list import IGNORE_POSTS

def test_is_ignored_prefix():
    IGNORE_POSTS.append("Breaking news:")
    assert _is_ignored_prefix("Breaking news: Something happened")
    
    assert _is_ignored_prefix("Breaking newz: Something happened")
    assert _is_ignored_prefix("Breaking news! Something happened")
    
    assert not _is_ignored_prefix("Regular news: Something happened")
    
    assert not _is_ignored_prefix("Today's breaking news: Something happened")

def test_is_duplicate_message_with_exact_match(posted_q):
    message = "Test message"
    posted_q.append(message)
    
    assert is_duplicate_message(message, posted_q)

def test_is_duplicate_message_with_similar_message(posted_q):
    posted_q.append("Original test message")
    
    similar_message = "Original test massage"
    assert is_duplicate_message(similar_message, posted_q)

def test_is_duplicate_message_with_different_message(posted_q):
    posted_q.append("Original test message")
    
    different_message = "Completely different text"
    assert not is_duplicate_message(different_message, posted_q)

def test_is_duplicate_message_with_empty_queue(posted_q):
    message = "Test message"
    
    assert not is_duplicate_message(message, posted_q) 