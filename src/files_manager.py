import os
import sqlite3

import requests
import time
from io import BytesIO
from PIL import Image

from src.static.settings import COUNT_UNIQUE_MESSAGES
from src.static.sources import tmp_folder, storage


async def save_published_message(lock, text):
    async with lock:
        conn = sqlite3.connect(storage)
        cursor = conn.cursor()

        cursor.execute('INSERT OR IGNORE INTO messages (text) VALUES (?)', (text,))
        conn.commit()

        cursor.execute('SELECT COUNT(text) FROM messages')
        count_unique = cursor.fetchone()[0]

        if count_unique > COUNT_UNIQUE_MESSAGES:
            excess = count_unique - COUNT_UNIQUE_MESSAGES
            cursor.execute('''
                DELETE FROM messages
                WHERE id IN (
                    SELECT id FROM messages
                    ORDER BY id ASC
                    LIMIT ?
                )
            ''', (excess,))
            conn.commit()
        conn.close()


def get_published_messages():
    conn = sqlite3.connect(storage)
    cursor = conn.cursor()
    cursor.execute('SELECT text FROM messages')
    rows = cursor.fetchall()
    messages = [row[0] for row in rows]
    conn.close()
    return messages


def clean_tmp_folder():
    for filename in os.listdir(tmp_folder):
        if filename != ".gitkeep":
            file_path = os.path.join(tmp_folder, filename)
            os.remove(file_path)


class SaveFileUrl:
    def __init__(self, url):
        self.url = url

    async def __call__(self):
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
