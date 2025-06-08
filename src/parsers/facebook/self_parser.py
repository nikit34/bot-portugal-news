import re

import requests
from src.producers.repeater import retry
from src.static.settings import KEY_SEARCH_LENGTH_CHARS
import logging

logger = logging.getLogger(__name__)


def get_facebook_published_messages(graph, context, max_posts):
    url = "https://graph.facebook.com/v18.0/" + context['self']['facebook_page_id'] + "/posts"
    params = {
        'access_token': graph.access_token,
        'limit': 50,
        'fields': 'message,created_time'
    }

    messages = []

    while max_posts > 0:
        try:
            data = _fetch_posts(url, params)
            posts = data.get('data', [])

            new_messages, max_posts = _extract_messages(posts, max_posts)
            messages.extend(new_messages)

            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                params = {}
            else:
                break
        except Exception as e:
            logger.error(f"Error fetching Facebook posts: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.content}")
            break

    return messages


@retry()
def _fetch_posts(url, params):
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _extract_messages(posts, max_posts):
    messages = []
    for post in posts:
        if 'message' in post:
            head = _process_message(post)
            messages.append(head)
            max_posts -= 1
            if max_posts == 0:
                break
    return messages, max_posts


def _process_message(post):
    message = post['message']
    message_without_url = re.sub(r'http[s]?://\S+', '', message)
    cleaned_message = re.sub(r'\n+', ' ', message_without_url).strip()
    return cleaned_message[:KEY_SEARCH_LENGTH_CHARS].strip()
