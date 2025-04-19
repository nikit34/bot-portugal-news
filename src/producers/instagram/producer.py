import requests
import logging

from src.producers.repeater import async_retry, retry
from src.producers.text_editor import trunc_str
from src.static.settings import INSTAGRAM_MAX_LENGTH_MESSAGE
from src.static.sources import self_instagram_channel

logger = logging.getLogger('app')


async def _upload_media(access_token, message, media_url):
    upload_url = 'https://graph.facebook.com/v20.0/' + self_instagram_channel + '/media'
    data = {
        'image_url': media_url,
        'caption': message,
        'access_token': access_token,
    }
    response = requests.post(upload_url, data=data)
    response.raise_for_status()
    return response.json().get('id')


async def _publish_media(access_token, media_id):
    publish_url = 'https://graph.facebook.com/v20.0/' + self_instagram_channel + '/media_publish'
    params = {
        'creation_id': media_id,
        'access_token': access_token
    }
    response = requests.post(publish_url, data=params)
    response.raise_for_status()
    return response.json()


async def _add_comment(access_token, media_id, message):
    url = 'https://graph.facebook.com/v20.0/' + media_id + '/comments'
    params = {
        'message': message,
        'access_token': access_token
    }
    response = requests.post(url, data=params)
    response.raise_for_status()


@retry()
def instagram_prepare_post(translated_message):
    return trunc_str(translated_message, INSTAGRAM_MAX_LENGTH_MESSAGE)


@async_retry()
async def instagram_send_message(graph, message, url_path):
    access_token = graph.access_token
    media_url = url_path.get('url')
    media_id = await _upload_media(access_token, message, media_url)
    return await _publish_media(access_token, media_id)
