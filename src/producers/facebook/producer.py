import pyshorteners

from src.producers.repeater import retry
from src.static.settings import FACEBOOK_MAX_LENGTH_MESSAGE
from src.text_editor import trunc_str


def facebook_prepare_post(translated_message, link):
    shortener = pyshorteners.Shortener()
    shorted_link = shortener.tinyurl.short(link)
    return trunc_str(translated_message, FACEBOOK_MAX_LENGTH_MESSAGE) + '\n\n' + shorted_link


@retry()
async def facebook_send_message(graph, message, file):
    return graph.put_photo(image=open(file, 'rb'), message=message)


@retry()
async def facebook_send_translated_respond(graph, flag, post, translated_text):
    graph.put_object(parent_object=post.get('id'), connection_name="comments", message=flag + ' ' + trunc_str(translated_text, FACEBOOK_MAX_LENGTH_MESSAGE))
