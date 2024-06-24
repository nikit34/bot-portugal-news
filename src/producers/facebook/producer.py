import pyshorteners
import requests

from src.producers.repeater import retry, async_retry
from src.static.settings import FACEBOOK_MAX_LENGTH_MESSAGE
from src.static.sources import self_facebook_page_id
from src.producers.text_editor import trunc_str


@retry(timeout=4)
def facebook_prepare_post(translated_message, link):
    shortener = pyshorteners.Shortener()
    shorted_link = shortener.tinyurl.short(link)
    return trunc_str(translated_message, FACEBOOK_MAX_LENGTH_MESSAGE) + '\n\n' + shorted_link


@async_retry()
async def facebook_send_message(graph, message, image):
    if not image.lower().endswith(".mp4"):
        return graph.put_photo(image=open(image, 'rb'), message=message)
    return send_video(graph, message, image)


@async_retry()
async def facebook_send_translated_respond(graph, flag, post, translated_text):
    graph.put_object(
        parent_object=post.get('id'),
        connection_name="comments",
        message=flag + ' ' + trunc_str(translated_text, FACEBOOK_MAX_LENGTH_MESSAGE)
    )


@retry()
def send_video(graph, message, video_path):
    url = 'https://graph.facebook.com/v20.0/' + self_facebook_page_id + '/videos'

    video_data = {
        'description': message,
        'access_token': graph.access_token,
    }
    with open(video_path, 'rb') as file:
        files = {
            'file': file
        }
        response = requests.post(url, data=video_data, files=files)
    response.raise_for_status()
    return response.json()
