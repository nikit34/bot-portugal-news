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
)

logger = logging.getLogger('app')


class VideoSkip(Exception):
    """Видео сознательно пропущено (слишком большое/недоступный формат).

    Не ошибка пайплайна — источник ловит её и логирует на debug, а не как сбой.
    """

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
