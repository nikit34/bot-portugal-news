import asyncio
import os
import logging
import requests
import time
from io import BytesIO
from PIL import Image

from src.static.sources import tmp_folder
from src.static.settings import (
    HTTP_REQUEST_TIMEOUT,
    MAX_VIDEO_SIZE_MB,
    YOUTUBE_FORMAT,
    YOUTUBE_MAX_VIDEO_DURATION_SECONDS,
    YOUTUBE_COOKIES_FILE,
    VIDEO_DOWNLOAD_TIMEOUT_SECONDS,
)

logger = logging.getLogger('app')


class VideoSkip(Exception):
    """Видео сознательно пропущено (слишком длинное/большое/недоступный формат).

    Не ошибка пайплайна — источник ловит её и логирует на debug, а не как сбой.
    """


def _ytdlp_downloaded_path(ydl, info):
    # Достаём путь скачанного файла из info-словаря yt-dlp устойчиво к версиям:
    # сперва requested_downloads[].filepath (актуальный путь после постобработки),
    # затем info['filepath'], в последнюю очередь восстанавливаем из шаблона.
    if not info:
        return None
    for req in (info.get('requested_downloads') or []):
        if req.get('filepath'):
            return req['filepath']
    if info.get('filepath'):
        return info['filepath']
    try:
        return ydl.prepare_filename(info)
    except Exception:
        return None

# A current browser User-Agent for image downloads. The bare request the bot used
# before sent no UA; a modern UA is more widely accepted by image CDNs. (Note: this
# does NOT defeat IP-based hotlink protection — e.g. zerozero.pt blocks datacenter
# IPs outright, header-independent.)
_IMAGE_DOWNLOAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def clean_tmp_folder():
    logger.info("Starting cleanup of temporary folder")
    for filename in os.listdir(tmp_folder):
        if filename != ".gitkeep":
            file_path = os.path.join(tmp_folder, filename)
            try:
                os.remove(file_path)
                logger.debug(f"Successfully removed file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {str(e)}")
    logger.info("Temporary folder cleanup completed")


class SaveFileUrl:
    def __init__(self, url):
        self.url = url
        logger.debug(f"Initialized SaveFileUrl with URL: {url}")

    async def __call__(self):
        return await asyncio.to_thread(self._download_and_save)

    def _download_and_save(self):
        try:
            logger.info(f"Downloading file from URL: {self.url}")
            # Send a modern UA and bound the request with a timeout (was unbounded).
            response = requests.get(
                self.url, headers=_IMAGE_DOWNLOAD_HEADERS, timeout=HTTP_REQUEST_TIMEOUT)
            response.raise_for_status()

            image = Image.open(BytesIO(response.content))
            image_path = tmp_folder + '/' + str(time.time_ns()) + '.png'
            image.save(image_path)
            logger.info(f"File successfully saved to: {image_path}")

            url_path = {
                "url": self.url,
                "path": image_path
            }
            return url_path
        except Exception as e:
            logger.error(f"Error saving file from URL {self.url}: {str(e)}")
            raise


class SaveVideoUrl:
    """Качает ПРЯМОЙ видео-URL (mp4-enclosure из RSS) в локальный .mp4.

    В отличие от SaveFileUrl НЕ прогоняет байты через PIL (это видео, не картинка):
    стримит в файл, обрывая закачку, если размер перевалил за MAX_VIDEO_SIZE_MB —
    чтобы кривой/огромный enclosure не съел диск и бюджет прогона.
    """

    def __init__(self, url):
        self.url = url
        logger.debug(f"Initialized SaveVideoUrl with URL: {url}")

    async def __call__(self):
        return await asyncio.to_thread(self._download_and_save)

    def _download_and_save(self):
        limit_bytes = MAX_VIDEO_SIZE_MB * 1024 * 1024
        video_path = tmp_folder + '/' + str(time.time_ns()) + '.mp4'
        logger.info(f"Downloading video from URL: {self.url}")
        try:
            with requests.get(
                self.url, headers=_IMAGE_DOWNLOAD_HEADERS,
                timeout=HTTP_REQUEST_TIMEOUT, stream=True,
            ) as response:
                response.raise_for_status()
                downloaded = 0
                with open(video_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1 << 16):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if downloaded > limit_bytes:
                            raise VideoSkip(
                                f"video {self.url} exceeds {MAX_VIDEO_SIZE_MB}MB cap")
                        f.write(chunk)
            logger.info(f"Video successfully saved to: {video_path}")
            return {"url": self.url, "path": video_path}
        except Exception:
            if os.path.exists(video_path):
                os.remove(video_path)
            raise


class SaveYouTubeVideo:
    """Скачивает ролик YouTube в локальный .mp4 через yt-dlp.

    yt-dlp импортируем лениво (тяжёлая опциональная зависимость; тесты её не трогают).
    Длинные ролики (полные матчи) и слишком большие файлы отсекаем через duration/
    filesize-фильтры yt-dlp → если формат не прошёл, файла нет и поднимаем VideoSkip
    (источник проглотит). Любой сбой yt-dlp (бот-проверка YouTube в CI и т.п.) тоже
    оборачиваем в VideoSkip — пайплайн fail-open, прогон не валится.
    """

    def __init__(self, url):
        self.url = url
        logger.debug(f"Initialized SaveYouTubeVideo with URL: {url}")

    async def __call__(self):
        return await asyncio.to_thread(self._download_and_save)

    def _download_and_save(self):
        import yt_dlp  # ленивый импорт: опциональная зависимость

        out_tmpl = tmp_folder + '/' + str(time.time_ns()) + '.%(ext)s'
        ydl_opts = {
            'format': YOUTUBE_FORMAT,
            'outtmpl': out_tmpl,
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': VIDEO_DOWNLOAD_TIMEOUT_SECONDS,
            'max_filesize': MAX_VIDEO_SIZE_MB * 1024 * 1024,
            'match_filter': yt_dlp.utils.match_filter_func(
                f'duration <= {YOUTUBE_MAX_VIDEO_DURATION_SECONDS}'),
        }
        if YOUTUBE_COOKIES_FILE:
            ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE

        logger.info(f"Downloading YouTube video: {self.url}")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                path = _ytdlp_downloaded_path(ydl, info)
        except Exception as e:
            raise VideoSkip(f"yt-dlp failed for {self.url}: {e}")

        if not path or not os.path.exists(path):
            # match_filter (длина) / max_filesize отсекли формат → файла нет
            raise VideoSkip(
                f"YouTube video {self.url} skipped (too long/large or unavailable)")
        if not path.lower().endswith('.mp4'):
            # FB /videos, IG Reels и Stories требуют mp4/h264 — иной контейнер не шлём
            os.remove(path)
            raise VideoSkip(f"YouTube video {self.url} not mp4 ({path}); skipping")
        logger.info(f"YouTube video successfully saved to: {path}")
        return {"url": self.url, "path": path}


class SaveFileTelegram:
    def __init__(self, getter_client, message):
        self.getter_client = getter_client
        self.message = message
        logger.debug(f"Initialized SaveFileTelegram with message: {message.id}")

    async def __call__(self):
        try:
            url = self.message.media
            logger.info(f"Downloading Telegram media: {url}")
            path = await self.getter_client.download_media(url, file=tmp_folder)
            logger.info(f"Telegram media successfully saved to: {path}")
            
            url_path = {
                "url": url,
                "path": path
            }
            return url_path
        except Exception as e:
            logger.error(f"Error saving Telegram media: {str(e)}")
            raise
