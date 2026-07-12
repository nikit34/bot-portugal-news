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

# Максимальный размер видео в мегабайтах. Публикация видео давно умеет всё, но
# слишком крупный клип (1080p/длинный) раньше резался на 50 МБ. Поднят до 200 МБ,
# чтобы проходило больше клипов; тюнится через env (загрузка/ре-энкод/аплоуд крупных
# видео дольше — держите в пределах бюджета прогона и лимитов IG Reels).
MAX_VIDEO_SIZE_MB = int(os.getenv('MAX_VIDEO_SIZE_MB', '200'))

# === Видео-источники =========================================================
# Публикация видео давно умеет всё (FB /videos + /video_stories, IG Reels + video
# stories, Telegram нативно). Видео из Telegram-каналов течёт всегда (telethon
# скачивает любое медиа). VIDEO_ENABLED — общий выключатель видео-добычи.
VIDEO_ENABLED = os.getenv('VIDEO_ENABLED', 'true').lower() not in ('0', 'false', 'no')

# Доставать прямое видео (mp4-enclosure / <media:content medium="video">) из RSS.
# Дёшево и безопасно, но текущие новостные фиды (BBC/Guardian/RTP/ge.globo) прямого
# видео НЕ отдают (только картинки) — сработает лишь если фид реально несёт mp4.
RSS_VIDEO_ENABLED = os.getenv('RSS_VIDEO_ENABLED', 'true').lower() not in ('0', 'false', 'no')

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

# Дублировать каждый успешный пост FB-страницы ещё и в Stories (эфемерны, 24ч) —
# как у Instagram, гонит заходы на страницу. Best-effort: ошибка Stories не валит и
# не ретраит основную публикацию в ленту (иначе @async_retry перевыложит пост дублем).
# ВНИМАНИЕ: Story требует прав на публикацию у Page-токена и считается отдельной
# публикацией к лимитам Meta; ловите рейт-лимит (срабатывает circuit breaker) —
# выключите. Фото-сторис: фото грузится НЕопубликованным и публикуется через
# /photo_stories; видео-сторис: resumable-загрузка через /video_stories.
FACEBOOK_STORIES_ENABLED = (
    os.getenv('FACEBOOK_STORIES_ENABLED', 'true').lower() not in ('0', 'false', 'no'))

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

# Прожиг заголовка поста прямо в КАРТИНКУ сторис (FB photo_stories и IG image
# stories). Эндпоинты Stories не принимают подпись/текст — единственный способ
# дать сторис текст — отрендерить его в само изображение (Pillow, 9:16). Видео-
# сторис не трогаем (нужен ffmpeg). Best-effort: ошибка рендера/неподходящее
# медиа => грузим оригинал без текста, основная публикация в ленту не страдает.
STORY_TEXT_OVERLAY_ENABLED = (
    os.getenv('STORY_TEXT_OVERLAY_ENABLED', 'true').lower() not in ('0', 'false', 'no'))
# Бренд-плашка (жёлтый кикер) над заголовком. Пусто => плашки нет, только заголовок.
STORY_OVERLAY_BRAND = os.getenv('STORY_OVERLAY_BRAND', '')
# Максимум символов заголовка на сторис (первая фраза поста, режется по слову).
STORY_HEADLINE_MAX_CHARS = int(os.getenv('STORY_HEADLINE_MAX_CHARS', '90'))

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

# === Graph API версия =======================================================
# Единая версия для ВСЕХ вызовов Graph/Instagram API (чтение и публикация). v18
# (2023) устарела; новые метрики инсайтов (IG shares/sends, views, reels-досмотр)
# отдаются только на свежих версиях. Меняется ОДНИМ местом; можно переопределить
# через GRAPH_API_VERSION (откатить на 'v21.0' или поднять — без правки кода).
GRAPH_API_VERSION = os.getenv('GRAPH_API_VERSION', 'v22.0')
GRAPH_API_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}/'
# Резюмируемый аплоуд IG reels/video живёт на отдельном хосте; версия — та же.
GRAPH_UPLOAD_BASE = f'https://rupload.facebook.com/ig-api-upload/{GRAPH_API_VERSION}/'

# === Уникализация контента (брендинг + анти-дубликат) =======================
# Прожигаем в каждое медиа имя нашего канала (вотермарка) и слегка меняем само
# изображение/видео (кроп, джиттер яркости/контраста/цвета, ре-энкод, срез EXIF/
# метаданных), чтобы перцептивный хэш и реверс-поиск не сматчили наш репост с
# оригиналом источника. Картинки — Pillow; видео — ffmpeg (бинарь из imageio-ffmpeg
# или системный). Применяется в serve() ПОСЛЕ фильтров, ДО публикации; результат
# уходит во все платформы (и в сторис-оверлей как основа).
UNIQUIFY_ENABLED = os.getenv('UNIQUIFY_ENABLED', 'true').lower() not in ('0', 'false', 'no')
UNIQUIFY_IMAGE_ENABLED = os.getenv('UNIQUIFY_IMAGE_ENABLED', 'true').lower() not in ('0', 'false', 'no')
# Видео-уникализация требует ffmpeg и ре-энкода (десятки секунд) — отдельный флаг.
UNIQUIFY_VIDEO_ENABLED = os.getenv('UNIQUIFY_VIDEO_ENABLED', 'true').lower() not in ('0', 'false', 'no')

# Вотермарка с именем канала. Пусто => берём @handle из self.telegram_channel.
# ВЫКЛ по умолчанию: видимая (тем более кросс-платформенная) вотермарка — это
# документированный сигнал подавления охвата и признак «неоригинального» контента
# в кранче оригинальности Meta 2025-2026, т.е. не щит, а лиабилити. Остальной слой
# уникализации (кроп/джиттер/ре-энкод/срез EXIF) не трогаем. Включить обратно:
# WATERMARK_ENABLED=true.
WATERMARK_ENABLED = os.getenv('WATERMARK_ENABLED', 'false').lower() not in ('0', 'false', 'no')
WATERMARK_TEXT = os.getenv('WATERMARK_TEXT', '')
# Непрозрачность вотермарки 0..1 (0.55 = заметно, но не перекрывает кадр).
WATERMARK_OPACITY = float(os.getenv('WATERMARK_OPACITY', '0.55'))

# Таймаут ffmpeg-ре-энкода одного видео (секунды) — чтобы зависший процесс не съел
# бюджет прогона; по истечении возвращаем оригинал (fail-open).
VIDEO_UNIQUIFY_TIMEOUT_SECONDS = int(os.getenv('VIDEO_UNIQUIFY_TIMEOUT_SECONDS', '120'))

# Потолок разрешения при ре-энкоде видео (длинная сторона, px). Крупный клип (после
# поднятия MAX_VIDEO_SIZE_MB до 200) в исходном 1080p/4K ре-энкодился бы минутами и
# грузился бы огромным файлом — один такой клип съедал бы окно дренажа фазы-2 и мог
# упереться в таймаут (тогда fail-open публикует БЕЗ вотермарки). Ограничение до
# ~720p делает ре-энкод дёшево-ограниченным и аплоуд лёгким — стандарт для соцсетей,
# плюс лишний сдвиг против дедупликации. НЕ апскейлит (мелкие клипы не трогает).
# 0 => без ограничения (ре-энкод в исходном разрешении).
UNIQUIFY_VIDEO_MAX_DIM = int(os.getenv('UNIQUIFY_VIDEO_MAX_DIM', '1280'))

# Контент-фильтр: пропускать посты с запрещённой лексикой/рекламой (см. blocklist.py)
CONTENT_FILTER_ENABLED = True

# Тематический фильтр: бот про футбол, но часть RSS-фидов общеспортивные и тянут
# F1/теннис/НБА и т.п. — отсекаем посты про другие виды спорта (см. topic_filter.py).
TOPIC_FILTER_ENABLED = os.getenv('TOPIC_FILTER_ENABLED', 'true').lower() not in ('0', 'false', 'no')

# Фильтр низкокачественных картинок: отсекаем мелкие превью/миниатюры (напр.
# 142x100 из RSS-фида), которые в ленте выглядят плохо. Порог по сторонам в px,
# fail-open: не смогли прочитать размер — не фильтруем. Настраивается через env.
IMAGE_QUALITY_FILTER_ENABLED = os.getenv('IMAGE_QUALITY_FILTER_ENABLED', 'true').lower() not in ('0', 'false', 'no')
IMAGE_MIN_WIDTH = int(os.getenv('IMAGE_MIN_WIDTH', '500'))
IMAGE_MIN_HEIGHT = int(os.getenv('IMAGE_MIN_HEIGHT', '300'))

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

# Суточный лимит постов в Instagram (по UTC-дню, копится в state-файле). Каждый
# IG-пост — это feed + (если включено) Stories = ~2 публикации к лимиту IG ~25/24ч.
# При достижении лимита IG пропускаем (FB/TG продолжают), чтобы не словить рейт-лимит
# Meta и не открыть общий circuit breaker, который зарежет и Facebook.
INSTAGRAM_DAILY_POST_LIMIT = int(os.getenv('INSTAGRAM_DAILY_POST_LIMIT', '12'))

# Бюджет времени на прогон (секунды). «Пустые» прогоны (нет свежего контента) иначе
# скрейпят все источники до упора; по истечении бюджета парсеры перестают брать
# новые записи. Меньше CI-таймаута (15м), с запасом на дайджест/сохранение состояния.
RUN_TIME_BUDGET_SECONDS = int(os.getenv('RUN_TIME_BUDGET_SECONDS', '540'))

# Слать ли краткий итог прогона в debug-чат (что/куда опубликовано, что отфильтровано
# и что молча упало — первый комментарий, Stories, права на insights). По умолчанию вкл;
# шлём только когда есть о чём (были публикации или сбои), чтобы не спамить пустыми.
RUN_SUMMARY_ENABLED = os.getenv('RUN_SUMMARY_ENABLED', 'true').lower() not in ('0', 'false', 'no')


def _flag(name, default):
    # Единый парсер булевых env-флагов: '1/true/yes/on' => True (без учёта регистра).
    return os.getenv(name, default).lower() in ('1', 'true', 'yes', 'on')


# === Оптимизация роста FB-канала ============================================
# Набор рычагов «вытащить максимум охвата/подписчиков». Все НОВЫЕ поведения — за
# флагами, по умолчанию ВЫКЛ (кроме чистых анти-демоут защит), чтобы включать и
# откатывать через env без правок кода. Подробности — в memory/fb-growth-optimization.

# --- Caption guard: чистим исходящую подпись от кликбейта/engagement-bait ----
# Meta аккаунт-уайд режет страницы за bait ('comente SIM', 'marque um amigo',
# КАПС-крик). Это анти-демоут защита, поэтому по умолчанию ВКЛ. Матчим по
# нормализованной форме, режем по оригиналу (акценты/регистр публикации сохраняем).
CAPTION_GUARD_ENABLED = _flag('CAPTION_GUARD_ENABLED', 'true')

# --- Хэштеги: на FB режем до немногих, биасим на сущности (клуб/игрок) --------
# На FB >5 меток читается как спам; 2-3 по делу — вторичный путь тематич. матча.
HASHTAG_MAX_FB = int(os.getenv('HASHTAG_MAX_FB', '3'))
# Поднимать распознанные сущности (ORG/PER) выше частотных существительных и
# допускать их в метки даже при единичном упоминании (имена в новостях редко
# повторяются). Пустой набор сущностей => поведение идентично прежнему.
HASHTAG_ENTITY_BIAS_ENABLED = _flag('HASHTAG_ENTITY_BIAS_ENABLED', 'true')
# Стабильная нишевая метка, добавляется первой (напр. лига/регион). Пусто => нет.
HASHTAG_NICHE_TAG = os.getenv('HASHTAG_NICHE_TAG', '')

# --- Карточки оригинальной графики (fee/transfer) -----------------------------
# Своя сгенерированная графика — единственный бесплатный value-add против
# unoriginal-content демоута и сама по себе save/share-worthy. v1: только карточки
# трансферов/сумм (направление однозначно), счёт пока не рендерим. По умолчанию ВЫКЛ.
CARDS_ENABLED = _flag('CARDS_ENABLED', 'false')

# --- Opinion-CTA: живой вопрос под постом (драйвер комментариев) ---------------
# FB ценит вдумчивые комменты выше лайков; живой открытый вопрос НЕ engagement-bait.
# Гард зашит в саму библиотеку (никаких 'comente SIM'). По умолчанию ВЫКЛ (риск
# выглядеть шаблонно/спамно — включать осознанно).
CTA_ENABLED = _flag('CTA_ENABLED', 'false')
# Дробный гейт: CTA добавляется лишь к ДОЛЕ постов (детерминированно по хешу текста
# поста — идемпотентно между прогонами), чтобы вопрос не висел под каждым постом и
# не читался как шаблонный engagement-bait. 1.0 = на каждом посте с сущностью, 0 = выкл.
CTA_EMISSION_RATE = float(os.getenv('CTA_EMISSION_RATE', '0.5'))

# --- Story-gate: не зеркалить КАЖДЫЙ пост в сторис вслепую ---------------------
# Сторис не доходят до НЕ-подписчиков (только retention) и каждая = доп.публикация
# к лимиту IG. Гейтим сторис здоровьем суточного IG-бюджета (тесните лимит — режем
# сторис первыми). По умолчанию ВЫКЛ (сохраняем текущее «зеркалим всё»).
STORY_GATE_ENABLED = _flag('STORY_GATE_ENABLED', 'false')
# Доля суточного IG-лимита, ВЫШЕ которой сторис подавляются (бережём слоты ленты).
STORY_GATE_IG_BUDGET_FRACTION = float(os.getenv('STORY_GATE_IG_BUDGET_FRACTION', '0.75'))

# --- Best-K ranker: тратим дефицитные слоты на лучшие новости -----------------
# Сейчас публикуются первые MAX_POSTS_PER_RUN прошедших фильтры (FIFO). Ранкер
# копит кандидатов и публикует топ-K по скору (выученный охват источника/часа +
# видео-бонус + длина заголовка − кликбейт). Тяжёлая работа (uniquify) — только для
# победителей. По умолчанию ВЫКЛ (поведение байт-в-байт = текущий FIFO).
RANKER_ENABLED = _flag('RANKER_ENABLED', 'false')
# Во сколько раз пул кандидатов больше бюджета постов (ограничивает скрейп в фазе 1).
# Расширен 4→8: больший пул продолжает скрейпить дальше высокоохватных фото-источников
# и доходит до Telegram-каналов с видео, чтобы видео вообще попадало в пул на отбор.
RANKER_POOL_FACTOR = int(os.getenv('RANKER_POOL_FACTOR', '8'))
# Бонус к скору кандидата-видео в best-K отборе. Видео-клипы обычно с короткой
# подписью (низкий length-бонус, нет выученных данных) и без этого проигрывают
# слот текстовым фото-постам. Бонус ~1.5 на шкале скора (~1.0 у среднего источника)
# уверенно поднимает видео в топ-K, когда оно есть, но сильное фото ещё может выиграть.
# 0 => видео не продвигается (чистый пул-эффект). Тюнится через env.
RANKER_VIDEO_BONUS = float(os.getenv('RANKER_VIDEO_BONUS', '1.5'))
# Сколько секунд wall-clock резервируем под фазу 2 (drain: скачивание+публикация
# топ-K) — фаза 1 (наполнение пула) останавливается раньше дедлайна на эту величину,
# чтобы на контент-богатом прогоне точно осталось время опубликовать лучших, а не
# упереться в дедлайн с полным пулом и нулём публикаций. ~K*(POST_DELAY+загрузка).
RANKER_DRAIN_RESERVE_SECONDS = int(os.getenv('RANKER_DRAIN_RESERVE_SECONDS', '180'))

# --- Engagement-weighted reward (вместо чистого reach) ------------------------
# reward = w_share*(shares+sends) + w_save*saves + w_comment*comments
#        + w_watch*avg_watch_sec + w_like*likes + w_reach*reach.
# 2026-переориентация под реальные сигналы ранжирования Meta: раздача (shares +
# sends/пересылки в DM), СОХРАНЕНИЯ и ДОСМОТР толкают охват к не-подписчикам, тогда
# как лайки — сигнал тщеславия. Поэтому shares↑, добавлены save/watch, а like ОБНУЛЁН.
# saves/watch тянутся из IG (у FB их на пост-уровне нет); sends — это IG-метрика
# `shares` (репост + отправка в личку). reach остаётся слабым хвостом.
# По умолчанию ВКЛ: учимся на вовлечённости, а не на чистом reach. Требует у токена
# instagram_manage_insights; если прав/метрики нет — fail-open (saves/shares/watch
# пустые, reward деградирует до comments+reach, не падает). Выключить: LEARNING_REWARD_ENABLED=false.
LEARNING_REWARD_ENABLED = _flag('LEARNING_REWARD_ENABLED', 'true')
LEARNING_W_SHARE = float(os.getenv('LEARNING_W_SHARE', '4.0'))
LEARNING_W_SAVE = float(os.getenv('LEARNING_W_SAVE', '3.0'))
LEARNING_W_COMMENT = float(os.getenv('LEARNING_W_COMMENT', '2.0'))
# watch — средний ДОСМОТР reels в СЕКУНДАХ (ig_reels_avg_watch_time / 1000); только
# видео, хвостовой сигнал, поэтому вес небольшой.
LEARNING_W_WATCH = float(os.getenv('LEARNING_W_WATCH', '0.3'))
# Лайки исключены из reward (слабо влияют на охват в 2026): дефолт 0. Вернуть вес
# можно через LEARNING_W_LIKE.
LEARNING_W_LIKE = float(os.getenv('LEARNING_W_LIKE', '0.0'))
LEARNING_W_REACH = float(os.getenv('LEARNING_W_REACH', '0.05'))

# --- dow-hour бакеты времени (день недели × час) ------------------------------
# Учим reward не только по часу UTC, но и по (день_недели × час) — вовлечённость
# в FB заметно выше по выходным и Чт/Пт. Partial pooling: hour_budget берёт fine
# dow-hour бакет, когда он хорошо просэмплирован, иначе откатывается на грубый
# hour-only (на низко-объёмном боте dow-hour ×7 разрежён). Накопление dow_hours
# идёт ВСЕГДА; влияет на бюджет только при LEARNING_TIME_BIAS_ENABLED.
LEARNING_DOW_HOUR_ENABLED = _flag('LEARNING_DOW_HOUR_ENABLED', 'true')

# --- UCB-ранжирование источников (explore/exploit) ----------------------------
# score = reward_avg + c * mean_reward * sqrt(ln(total_n)/n); c=0 => текущий greedy.
# Требует LEARNING_BIAS_ENABLED. По умолчанию ВЫКЛ (greedy avg-sort как сейчас).
LEARNING_BANDIT_ENABLED = _flag('LEARNING_BANDIT_ENABLED', 'false')
LEARNING_UCB_C = float(os.getenv('LEARNING_UCB_C', '0.7'))
# Минимум хорошо-сэмплированных источников, прежде чем биас начнёт отсекать
# нижние (иначе при тонких данных источники голодают). Аналог LEARNING_HOUR_MIN_SAMPLES.
LEARNING_SOURCE_MIN_SAMPLES = int(os.getenv('LEARNING_SOURCE_MIN_SAMPLES', '3'))

# --- FB post-level инсайты по сохранённым ID ----------------------------------
# GET /{post-id}/insights (post_impressions_unique) + поля объекта (shares,
# comments.summary, reactions.summary). Нужно право read_insights; best-effort,
# fail-open на IG-прокси. По умолчанию ВКЛ: даёт FB-репосты/комменты как reward-сигнал
# по сохранённому fb_id. Выключить: FB_POST_INSIGHTS_ENABLED=false.
FB_POST_INSIGHTS_ENABLED = _flag('FB_POST_INSIGHTS_ENABLED', 'true')

# --- A/B-логирование вариантов (measurement-only) -----------------------------
# Копим reward по media_type и числу хэштегов, показываем в дайджесте. Только
# измерение — в отбор не вмешивается. По умолчанию ВЫКЛ.
VARIANT_LOGGING_ENABLED = _flag('VARIANT_LOGGING_ENABLED', 'false')

# --- Scoring по TTL (не только в час дайджеста) -------------------------------
# Скорить созревшие посты на любом прогоне, если с прошлого скоринга прошло больше
# TTL — чтобы пропущенный/упавший прогон в час дайджеста не терял свежесть. Сам
# дайджест по-прежнему раз в сутки. По умолчанию ВЫКЛ (как сейчас — в час дайджеста).
LEARNING_SCORE_TTL_SECONDS = int(os.getenv('LEARNING_SCORE_TTL_SECONDS', str(20 * 3600)))
LEARNING_SCORE_BY_TTL_ENABLED = _flag('LEARNING_SCORE_BY_TTL_ENABLED', 'false')

# === TTS-озвучка (пивот на narrated-Reel, Фаза 0) ===========================
# Офлайн нейро-TTS (piper) для будущего narrated-Reel: озвучиваем факты новости
# своим голосом => контент оригинален ПО ПОСТРОЕНИЮ (Meta 2026 засчитывает
# добавленную озвучку как material edit, в отличие от watermark/uniquify). Piper
# работает на onnxruntime (уже в стеке) полностью офлайн — без подписок, сети и GPU.
# Модуль fail-open: нет piper или модели голоса => synthesize() вернёт None, и
# пайплайн откатится на текущее поведение. Реально подключается в Фазе 1 (reel.py);
# в Фазе 0 модуль ещё никто не вызывает.
TTS_ENABLED = _flag('TTS_ENABLED', 'true')
TTS_ENGINE = os.getenv('TTS_ENGINE', 'piper')
# Имя голоса piper: модель ищется как <TTS_VOICES_DIR>/<TTS_VOICE>.onnx (+ .onnx.json).
TTS_VOICE = os.getenv('TTS_VOICE', 'pt_BR-faber-medium')
# Каталог с вендоренными моделями голосов (рядом с fonts/). Переопределяется env.
TTS_VOICES_DIR = os.getenv('TTS_VOICES_DIR', os.path.join(os.path.dirname(__file__), 'voices'))
# Явный путь к .onnx (приоритетнее TTS_VOICE/DIR), если модель лежит вне каталога.
TTS_VOICE_PATH = os.getenv('TTS_VOICE_PATH', '')
# Потолок длины озвучиваемого текста (символы) — режем длинный пост в короткий Reel.
TTS_MAX_CHARS = int(os.getenv('TTS_MAX_CHARS', '600'))

# === narrated-Reel рендер (пивот, Фаза 1) ===================================
# Превращаем image/text-новость в вертикальный Reel: плашка 9:16 (story_overlay)
# + TTS-озвучка (tts.py) + лёгкий Ken Burns. Контент оригинален ПО ПОСТРОЕНИЮ =>
# для такого поста НЕ применяем watermark/uniquify. fail-open: нет piper/голоса/
# ffmpeg или любой сбой => None, откат на текущее поведение (карточка/фото + uniquify).
# OFF по умолчанию (opt-in; включать сперва на изолированном канале/доле постов).
REEL_RENDER_ENABLED = _flag('REEL_RENDER_ENABLED', 'false')
# Лёгкий зум (Ken Burns) — статичная плашка становится «видео» (буст в Reels +
# вклад в оригинальность). Выключить: REEL_MOTION_ENABLED=false (просто статичный кадр).
REEL_MOTION_ENABLED = _flag('REEL_MOTION_ENABLED', 'true')
# Жёсткий потолок длины Reel (сек) — страховка сверх TTS_MAX_CHARS.
REEL_MAX_SECONDS = float(os.getenv('REEL_MAX_SECONDS', '40'))
# Таймаут ffmpeg-сборки одного Reel (сек): зависший процесс не должен съесть бюджет
# прогона (таймаут CI-джобы 15 мин); по истечении — fail-open (публикуем как раньше).
REEL_RENDER_TIMEOUT_SECONDS = int(os.getenv('REEL_RENDER_TIMEOUT_SECONDS', '90'))
