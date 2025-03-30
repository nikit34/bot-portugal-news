import pytest
import time
from src.storage.redis_client import PostHistoryStorage

@pytest.fixture(scope="module")
def redis_storage():
    storage = PostHistoryStorage()
    storage.clear_history()  # Очищаем перед тестами
    return storage

def test_persistence_between_connections(redis_storage):
    # Добавляем сообщение
    test_message = "Test persistence message"
    redis_storage.add_post(test_message)
    
    # Создаем новое подключение
    new_storage = PostHistoryStorage()
    
    # Проверяем, что сообщение сохранилось
    recent_posts = new_storage.get_recent_posts()
    assert test_message[:50] in recent_posts

def test_data_persistence_after_restart(redis_storage):
    test_message = "Test message for restart"
    redis_storage.add_post(test_message)
    
    # Симулируем перезапуск сервиса
    time.sleep(1)  # Даем время на запись данных
    new_storage = PostHistoryStorage()
    
    recent_posts = new_storage.get_recent_posts()
    assert test_message[:50] in recent_posts 