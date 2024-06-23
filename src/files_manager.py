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


async def save_file_tmp_from_url(url):
    response = requests.get(url)
    response.raise_for_status()

    image = Image.open(BytesIO(response.content))

    image_path = tmp_folder + '/' + str(time.time()) + '.png'
    image.save(image_path)
    return image_path


async def save_file_tmp_from_telegram(getter_client, message):
    return await getter_client.download_media(message.media, file=tmp_folder)
