import os
import logging
import requests
import time
from io import BytesIO
from PIL import Image

from src.static.sources import tmp_folder

logger = logging.getLogger(__name__)


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
        try:
            logger.info(f"Downloading file from URL: {self.url}")
            response = requests.get(self.url)
            response.raise_for_status()

            image = Image.open(BytesIO(response.content))
            image_path = tmp_folder + '/' + str(time.time()) + '.png'
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
