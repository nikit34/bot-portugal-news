from time import sleep

from src.static.settings import TIMEOUT, MAX_LENGTH_MESSAGE, REPEAT_REQUESTS
from src.text_editor import trunc_str


def facebook_prepare_post(translated_message, source, link):
    title_post = '<a href="' + link + '">' + source + '</a>\n'
    return title_post + trunc_str(translated_message, MAX_LENGTH_MESSAGE)


async def facebook_send_message(graph, message, file, repeat=REPEAT_REQUESTS):
    try:
        return graph.put_photo(image=open(file, 'rb'), message=message)
    except Exception:
        if repeat > 0:
            sleep(TIMEOUT)
            repeat -= 1
            return facebook_send_message(graph, message, file, repeat)


async def facebook_send_translated_respond(graph, flag, post, translated_text):
    graph.put_object(parent_object=post.get('id'), connection_name="comments", message=flag + ' ' + trunc_str(translated_text, MAX_LENGTH_MESSAGE))
