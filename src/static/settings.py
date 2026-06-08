import os

# Максимальная длина поискового запроса в символах
KEY_SEARCH_LENGTH_CHARS = 50

# Максимальное количество уникальных сообщений для обработки
COUNT_UNIQUE_MESSAGES = 1000

# Время ожидания (таймаут) в секундах
TIMEOUT = 4

# Пороговое значение для определения схожести сообщений (от 0 до 1)
MESSAGE_SIMILARITY_THRESHOLD = 0.7

# Максимальное количество сообщений, которые будут обработаны
MAX_NUMBER_TAKEN_MESSAGES = 100

# Количество сообщений в одном пакете
MESSAGE_CHUNK_SIZE = 10

# Количество повторных попыток запроса
REPEAT_REQUESTS = 5

# Таймаут HTTP-запроса при дозагрузке страницы статьи (секунды)
HTTP_REQUEST_TIMEOUT = 15

# Дозагрузка страниц статей abola.pt: сайт сбрасывает соединения при большом числе
# одновременных запросов, поэтому ограничиваем параллелизм и повторяем при обрыве.
ABOLA_FETCH_CONCURRENCY = 4
ABOLA_FETCH_RETRIES = 1
ABOLA_FETCH_RETRY_DELAY = 1

# Максимальная длина тела ответа, добавляемого в уведомление об ошибке (символы).
# Полная HTML-страница ошибки превысила бы лимит Telegram sendMessage (4096 символов),
# и само уведомление упало бы с 400 Bad Request, так и не дойдя до чата.
MAX_ERROR_RESPONSE_CHARS = 500

# Минимальное количество ключевых слов для обработки
MINIMUM_NUMBER_KEYWORDS = 20

# Максимальный размер видео в мегабайтах
MAX_VIDEO_SIZE_MB = 50

# Максимальное количество ключевых слов для использования
MAX_COUNT_KEYWORDS = 5

# Пороговое значение веса для ключевых слов
WEIGHT_KEYWORDS_THRESHOLD = 2

# Целевой язык для обработки (португальский)
TARGET_LANGUAGE = 'pt'

# Максимальная длина сообщения для Telegram (в символах)
# Ограничение платформы на длину одного поста
TELEGRAM_MAX_LENGTH_MESSAGE = 1000

# Максимальная длина сообщения для Facebook (в символах)
# Лимит на количество символов в одном посте Facebook
FACEBOOK_MAX_LENGTH_MESSAGE = 6000

# Максимальная длина сообщения для Instagram (в символах)
# Максимально допустимое количество символов в посте Instagram
INSTAGRAM_MAX_LENGTH_MESSAGE = 5000

# Контент-фильтр: пропускать посты с запрещённой лексикой/рекламой (см. blocklist.py)
CONTENT_FILTER_ENABLED = True

# NSFW-фильтр картинок через nudenet (локально). При ошибке детектора — fail-open.
IMAGE_NSFW_ENABLED = os.getenv('IMAGE_NSFW_ENABLED', 'true').lower() not in ('0', 'false', 'no')
# Порог уверенности детектора для блокировки (0..1)
NSFW_SCORE_THRESHOLD = float(os.getenv('NSFW_SCORE_THRESHOLD', '0.5'))

# Троттлинг публикаций (защита от рейт-лимитов и банов). Настраивается через env
# (и через workflow_dispatch inputs), чтобы крутить значения без правок кода.
# Максимальное число постов за один запуск — бэклог сливается плавно, без всплесков
MAX_POSTS_PER_RUN = int(os.getenv('MAX_POSTS_PER_RUN', '3'))

# Пауза между публикациями в секундах — разносит посты во времени
POST_DELAY_SECONDS = int(os.getenv('POST_DELAY_SECONDS', '40'))
