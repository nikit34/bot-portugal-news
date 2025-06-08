import requests
import logging

from src.producers.repeater import async_retry, retry
from src.producers.text_editor import trunc_str
from src.static.settings import INSTAGRAM_MAX_LENGTH_MESSAGE

logger = logging.getLogger('app')


async def _upload_media(access_token, message, media_url, context):
    upload_url = 'https://graph.facebook.com/v18.0/' + context['self_instagram_channel'] + '/media'
    data = {
        'image_url': media_url,
        'caption': message,
        'access_token': access_token,
    }
    response = requests.post(upload_url, data=data)
    response.raise_for_status()
    return response.json().get('id')


async def _publish_media(access_token, media_id, context):
    publish_url = 'https://graph.facebook.com/v18.0/' + context['self_instagram_channel'] + '/media_publish'
    params = {
        'creation_id': media_id,
        'access_token': access_token
    }
    response = requests.post(publish_url, data=params)
    response.raise_for_status()
    return response.json()


@retry()
def instagram_prepare_post(translated_message):
    return trunc_str(translated_message, INSTAGRAM_MAX_LENGTH_MESSAGE)


@async_retry()
async def instagram_send_message(graph, message, url_path, context):
    access_token = graph.access_token
    media_url = url_path.get('url')
    media_id = await _upload_media(access_token, message, media_url, context)
    return await _publish_media(access_token, media_id, context)
