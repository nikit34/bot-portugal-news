import logging
from typing import List, Optional
import redis
from redis.exceptions import ConnectionError
import time
from src.static.settings import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD,
    COUNT_UNIQUE_MESSAGES,
    KEY_SEARCH_LENGTH_CHARS
)

logger = logging.getLogger(__name__)

class PostHistoryStorage:
    def __init__(self, max_retries: int = 3, retry_delay: int = 5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connect()
        self.posts_key = "published_posts"
        
    def _connect(self) -> None:
        """Устанавливает соединение с Redis с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                self.redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                self.redis_client.ping()  # Проверяем соединение
                logger.info("Successfully connected to Redis")
                break
            except (ConnectionError, redis.RedisError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to connect to Redis after {self.max_retries} attempts: {e}")
                    raise
                logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
                time.sleep(self.retry_delay)

    def add_post(self, message: str) -> None:
        """Добавляет пост в историю"""
        try:
            # Обрезаем сообщение до нужной длины
            head = message[:KEY_SEARCH_LENGTH_CHARS].strip()
            # Добавляем в начало списка
            self.redis_client.lpush(self.posts_key, head)
            # Обрезаем список до максимальной длины
            self.redis_client.ltrim(self.posts_key, 0, COUNT_UNIQUE_MESSAGES - 1)
            logger.debug(f"Added post to history: {head[:30]}...")
        except redis.RedisError as e:
            logger.error(f"Failed to add post to Redis: {e}")

    def get_recent_posts(self, count: Optional[int] = None) -> List[str]:
        """Получает последние посты из истории"""
        try:
            max_posts = count if count is not None else COUNT_UNIQUE_MESSAGES
            posts = self.redis_client.lrange(self.posts_key, 0, max_posts - 1)
            logger.debug(f"Retrieved {len(posts)} posts from history")
            return posts
        except redis.RedisError as e:
            logger.error(f"Failed to get posts from Redis: {e}")
            return []

    def clear_history(self) -> None:
        """Очищает историю постов"""
        try:
            self.redis_client.delete(self.posts_key)
            logger.info("Post history cleared")
        except redis.RedisError as e:
            logger.error(f"Failed to clear post history: {e}") 