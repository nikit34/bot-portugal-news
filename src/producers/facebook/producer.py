import asyncio
import requests

from src.producers.repeater import retry, async_retry
from src.static.settings import FACEBOOK_MAX_LENGTH_MESSAGE
from src.producers.text_editor import trunc_str
from src.producers.hashtags import extract_hashtags, append_hashtags


@retry()
def facebook_prepare_post(translated_message, doc):
    text_link = trunc_str(translated_message, FACEBOOK_MAX_LENGTH_MESSAGE)
    keywords = extract_hashtags(doc)
    return append_hashtags(text_link, keywords)


@async_retry()
async def facebook_send_message(graph, message, url_path, context):
    file_path = url_path.get("path")
    if not file_path.lower().endswith(".mp4"):
        return await asyncio.to_thread(_send_photo, graph, message, file_path)
    return await asyncio.to_thread(_send_video, graph, message, file_path, context)


def _send_photo(graph, message, file_path):
    with open(file_path, 'rb') as file:
        return graph.put_photo(image=file, message=message)


def _send_video(graph, message, file_path, context):
    url = 'https://graph.facebook.com/v18.0/' + context['self_facebook_page_id'] + '/videos'

    video_data = {
        'description': message,
        'access_token': graph.access_token,
    }
    with open(file_path, 'rb') as file:
        files = {
            'file': file
        }
        response = requests.post(url, data=video_data, files=files)
    response.raise_for_status()
    return response.json()
