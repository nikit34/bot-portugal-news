import os

import requests
import time
from io import BytesIO
from PIL import Image

from src.static.sources import tmp_folder


def clean_tmp_folder():
    for filename in os.listdir(tmp_folder):
        if filename != ".gitkeep":
            file_path = os.path.join(tmp_folder, filename)
            os.remove(file_path)


class SaveFileUrl:
    def __init__(self, url):
        self.url = url

    def __call__(self):
        response = requests.get(self.url)
        response.raise_for_status()

        image = Image.open(BytesIO(response.content))

        image_path = tmp_folder + '/' + str(time.time()) + '.png'
        image.save(image_path)
        url_path = {
            "url": self.url,
            "path": image_path
        }
        return url_path


class SaveFileTelegram:
    def __init__(self, getter_client, message):
        self.getter_client = getter_client
        self.message = message

    async def __call__(self):
        url = self.message.media
        url_path = {
            "url": url,
            "path": await self.getter_client.download_media(url, file=tmp_folder)
        }
        return url_path
