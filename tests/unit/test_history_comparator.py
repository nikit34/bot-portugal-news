from collections import deque
from src.processor.history_comparator import is_duplicate_message
from src.static.settings import COUNT_UNIQUE_MESSAGES

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