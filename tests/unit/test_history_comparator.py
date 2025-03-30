import pytest
from unittest.mock import Mock
from src.processor.history_comparator import is_duplicate_message
from src.storage.redis_client import PostHistoryStorage

@pytest.fixture
def mock_storage():
    storage = Mock(spec=PostHistoryStorage)
    return storage

def test_is_duplicate_message_with_exact_match(mock_storage):
    message = "Test message"
    mock_storage.get_recent_posts.return_value = [message]
    
    assert is_duplicate_message(message, mock_storage)

def test_is_duplicate_message_with_similar_message(mock_storage):
    mock_storage.get_recent_posts.return_value = ["Original test message"]
    
    similar_message = "Original test massage"
    assert is_duplicate_message(similar_message, mock_storage)

def test_is_duplicate_message_with_different_message(mock_storage):
    mock_storage.get_recent_posts.return_value = ["Original test message"]
    
    different_message = "Completely different text"
    assert not is_duplicate_message(different_message, mock_storage)

def test_is_duplicate_message_with_empty_queue(mock_storage):
    message = "Test message"
    
    assert not is_duplicate_message(message, mock_storage) 