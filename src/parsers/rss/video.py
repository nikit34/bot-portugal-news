import logging

logger = logging.getLogger('app')

# Расширения/типы, которые считаем прямым скачиваемым видео. HLS/DASH-манифесты
# (.m3u8/.mpd) НЕ берём — это не один файл, их без ffmpeg не склеить.
_VIDEO_EXTENSIONS = ('.mp4', '.mov', '.m4v', '.webm')


def _looks_like_video(url, type_, medium):
    if not url:
        return False
    type_ = (type_ or '').lower()
    medium = (medium or '').lower()
    if type_.startswith('video/'):
        return True
    if medium == 'video':
        return True
    base = url.split('?', 1)[0].lower()
    return base.endswith(_VIDEO_EXTENSIONS)


def extract_video_url(entry):
    """Достаёт URL ПРЯМОГО видео-файла из RSS-записи (feedparser entry), если есть.

    Сканируем media:content, enclosures и links на video/* mime, medium="video"
    или видео-расширение. Возвращаем первый подходящий URL или '' (видео нет).
    Только прямые файлы (mp4/mov/...), не страницы и не стриминговые манифесты —
    их умеет скачать SaveVideoUrl и принять FB/IG/Telegram.

    NB: магистральные новостные фиды (BBC/Guardian/RTP/ge.globo) прямого видео НЕ
    отдают (встроенный плеер) — для них функция честно вернёт ''.
    """
    # media:content — самый частый носитель медиавариантов в RSS
    for item in (entry.get('media_content') or []):
        url = item.get('url')
        if _looks_like_video(url, item.get('type'), item.get('medium')):
            logger.debug(f"[rss.video] media:content video: {url}")
            return url

    # enclosures + generic links с rel="enclosure"
    candidates = list(entry.get('enclosures') or [])
    candidates += [l for l in (entry.get('links') or []) if l.get('rel') == 'enclosure']
    for item in candidates:
        url = item.get('url') or item.get('href')
        if _looks_like_video(url, item.get('type'), None):
            logger.debug(f"[rss.video] enclosure video: {url}")
            return url

    return ''
