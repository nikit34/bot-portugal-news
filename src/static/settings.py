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

# Максимальная длина тела поста Instagram (в символах). Реальный лимит подписи
# IG — 2200 символов; режем тело до 2000, оставляя запас под хэштеги (в режиме,
# когда они дописываются в подпись), чтобы подпись не вышла за лимит.
INSTAGRAM_MAX_LENGTH_MESSAGE = 2000

# Размещение хэштегов в Instagram. False (по умолчанию) — дописываем хэштеги прямо
# в подпись (как для Facebook). True — публикуем чистую подпись, а хэштеги кладём
# первым комментарием (best practice). ВНИМАНИЕ: комментарий требует права
# instagram_manage_comments; у текущего токена его нет (CI: 400 на /comments),
# поэтому по умолчанию держим хэштеги в подписи. Выдадите право — включите True.
INSTAGRAM_HASHTAGS_AS_COMMENT = (
    os.getenv('INSTAGRAM_HASHTAGS_AS_COMMENT', 'false').lower() not in ('0', 'false', 'no'))

# Дублировать каждый успешный пост IG ещё и в Stories (эфемерны, 24ч) — гонит
# заходы в профиль. Best-effort: ошибка Stories не валит и не ретраит основную
# публикацию. ВНИМАНИЕ: Stories — дополнительные публикации, тоже считаются к
# лимитам IG; если ловите рейт-лимит (срабатывает circuit breaker) — выключите.
INSTAGRAM_STORIES_ENABLED = (
    os.getenv('INSTAGRAM_STORIES_ENABLED', 'true').lower() not in ('0', 'false', 'no'))

# Instagram Content Publishing API обрабатывает медиа-контейнер асинхронно: Meta
# сама скачивает image_url после POST /media. Публиковать (/media_publish) можно
# только когда контейнер перешёл в status_code=FINISHED — иначе прилетает
# 400 / code 9007 / subcode 2207027 ("Медиаданные не готовы к публикации").
# Поэтому между созданием и публикацией опрашиваем статус контейнера.
INSTAGRAM_MEDIA_POLL_ATTEMPTS = int(os.getenv('INSTAGRAM_MEDIA_POLL_ATTEMPTS', '15'))
INSTAGRAM_MEDIA_POLL_INTERVAL = float(os.getenv('INSTAGRAM_MEDIA_POLL_INTERVAL', '2'))

# Видео (Reels) Meta обрабатывает заметно дольше картинки (транскод), поэтому
# ждём готовности контейнера дольше: по умолчанию 30 × 4с = до 120с.
INSTAGRAM_VIDEO_POLL_ATTEMPTS = int(os.getenv('INSTAGRAM_VIDEO_POLL_ATTEMPTS', '30'))
INSTAGRAM_VIDEO_POLL_INTERVAL = float(os.getenv('INSTAGRAM_VIDEO_POLL_INTERVAL', '4'))

# Контент-фильтр: пропускать посты с запрещённой лексикой/рекламой (см. blocklist.py)
CONTENT_FILTER_ENABLED = True

# NSFW-фильтр картинок через nudenet (локально). При ошибке детектора — fail-open.
IMAGE_NSFW_ENABLED = os.getenv('IMAGE_NSFW_ENABLED', 'true').lower() not in ('0', 'false', 'no')
# Порог уверенности детектора для блокировки (0..1)
NSFW_SCORE_THRESHOLD = float(os.getenv('NSFW_SCORE_THRESHOLD', '0.5'))

# Insights-дайджест (охваты/вовлечённость) в debug-чат. Бот stateless и крутится
# каждые 2ч, поэтому шлём раз в сутки по совпадению UTC-часа (cron идёт по чётным
# часам — час по умолчанию чётный). Метрики берём щадящие к версиям Graph API:
# reach (endpoint insights, нужно право *_insights) + like_count/comments_count
# (обычные поля media); чего нет/на что нет прав — пропускаем без падения.
INSIGHTS_REPORT_ENABLED = os.getenv('INSIGHTS_REPORT_ENABLED', 'true').lower() not in ('0', 'false', 'no')
INSIGHTS_REPORT_HOUR = int(os.getenv('INSIGHTS_REPORT_HOUR', '8'))
INSIGHTS_MEDIA_LIMIT = int(os.getenv('INSIGHTS_MEDIA_LIMIT', '25'))
INSIGHTS_TOP_N = int(os.getenv('INSIGHTS_TOP_N', '10'))

# Обучение на охватах. Бот копит за прогонами среднюю reach по каждому источнику
# и (опционально) смещает отбор источников в пользу самых охватных. Состояние —
# JSON-файл; в CI переживает прогоны через actions/cache (без новой инфры/секретов).
LEARNING_STATE_PATH = os.getenv('LEARNING_STATE_PATH', 'state/insights_state.json')
# EW-сглаживание per-source reach (вес нового замера), 0 < alpha <= 1.
LEARNING_ALPHA = float(os.getenv('LEARNING_ALPHA', '0.3'))
# Через сколько секунд после публикации reach считаем «созревшим» для учёта.
LEARNING_MATURATION_SECONDS = int(os.getenv('LEARNING_MATURATION_SECONDS', str(24 * 3600)))
# Сколько ждём reach по посту, прежде чем выкинуть его из ожидания как анметч.
LEARNING_MAX_AGE_SECONDS = int(os.getenv('LEARNING_MAX_AGE_SECONDS', str(7 * 24 * 3600)))
# Приоритет ещё не оценённого источника при сортировке: inf => сначала исследуем
# новые источники, потом эксплуатируем выученные охваты.
LEARNING_DEFAULT_PRIOR = float(os.getenv('LEARNING_DEFAULT_PRIOR', 'inf'))
# Смещать ли отбор источников по выученным охватам. По умолчанию ВЫКЛ: данные
# копятся и попадают в дайджест, но поведение публикации не меняется, пока не
# накопится статистика и это не включат явно.
LEARNING_BIAS_ENABLED = os.getenv('LEARNING_BIAS_ENABLED', 'false').lower() in ('1', 'true', 'yes')

# Смещать ли число постов за прогон по выученному охвату ТЕКУЩЕГО часа (UTC): в
# «хорошие» часы публикуем больше, в «слабые» — меньше (но не ноль, чтобы бэклог
# дренировался и часы продолжали сэмплироваться). По умолчанию ВЫКЛ.
LEARNING_TIME_BIAS_ENABLED = os.getenv('LEARNING_TIME_BIAS_ENABLED', 'false').lower() in ('1', 'true', 'yes')
# Минимум замеров на час, чтобы учитывать его в смещении (иначе час считается
# недосэмплированным и получает полный бюджет — исследуем).
LEARNING_HOUR_MIN_SAMPLES = int(os.getenv('LEARNING_HOUR_MIN_SAMPLES', '3'))

# Троттлинг публикаций (защита от рейт-лимитов и банов). Настраивается через env
# (и через workflow_dispatch inputs), чтобы крутить значения без правок кода.
# Максимальное число постов за один запуск — бэклог сливается плавно, без всплесков
MAX_POSTS_PER_RUN = int(os.getenv('MAX_POSTS_PER_RUN', '3'))

# Пауза между публикациями в секундах — разносит посты во времени
POST_DELAY_SECONDS = int(os.getenv('POST_DELAY_SECONDS', '40'))
