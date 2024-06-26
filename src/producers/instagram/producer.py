import pyshorteners
import requests
import logging

from src.producers.repeater import async_retry, retry
from src.producers.text_editor import trunc_str
from src.static.settings import INSTAGRAM_MAX_LENGTH_MESSAGE
from src.static.sources import self_instagram_channel

logger = logging.getLogger(__name__)


async def _upload_media(access_token, message, media_url):
    upload_url = 'https://graph.facebook.com/v20.0/' + self_instagram_channel + '/media'
    data = {
        'image_url': media_url,
        'caption': message,
        'access_token': access_token,
    }
    response = requests.post(upload_url, data=data)
    return response.json().get('id')


async def _publish_media(access_token, media_id):
    publish_url = 'https://graph.facebook.com/v20.0/' + self_instagram_channel + '/media_publish'
    params = {
        'creation_id': media_id,
        'access_token': access_token
    }
    response = requests.post(publish_url, data=params)
    return response.json()


async def _add_comment(access_token, media_id, message):
    url = 'https://graph.facebook.com/v20.0/' + media_id + '/comments'
    params = {
        'message': message,
        'access_token': access_token
    }
    requests.post(url, data=params)


@retry(timeout=4)
def instagram_prepare_post(translated_message, link):
    shortener = pyshorteners.Shortener()
    shorted_link = shortener.tinyurl.short(link)
    return trunc_str(translated_message, INSTAGRAM_MAX_LENGTH_MESSAGE) + '\n\n' + shorted_link


@async_retry()
async def instagram_send_message(graph, message, url_path):
    access_token = graph.access_token
    media_url = url_path.get('url')
    media_id = await _upload_media(access_token, message, media_url)
    return await _publish_media(access_token, media_id)


@async_retry()
async def instagram_send_translated_respond(graph, flag, message_sent, translated_text):
    access_token = graph.get('access_token')
    message_id = message_sent.get('id')
    message = flag + ' ' + trunc_str(translated_text, INSTAGRAM_MAX_LENGTH_MESSAGE)
    await _add_comment(access_token, message_id, message)
