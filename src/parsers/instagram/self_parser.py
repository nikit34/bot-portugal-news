import requests
from src.producers.repeater import retry
from src.processor.history_comparator import make_head
from src.static.settings import GRAPH_API_BASE
from src.utils.notify import redact_secrets
import logging

logger = logging.getLogger(__name__)


def get_instagram_published_messages(graph, context, max_posts):
    url = GRAPH_API_BASE + context['self_instagram_channel'] + "/media"
    params = {
        'access_token': graph.access_token,
        'limit': 50,
        'fields': 'caption,timestamp'
    }

    messages = []

    while max_posts > 0:
        try:
            data = _fetch_media(url, params)
            posts = data.get('data', [])

            new_messages, max_posts = _extract_captions(posts, max_posts)
            messages.extend(new_messages)

            if 'paging' in data and 'next' in data['paging']:
                url = data['paging']['next']
                params = {}
            else:
                break
        except Exception as e:
            logger.error(redact_secrets(f"Error fetching Instagram media: {str(e)}"))
            if hasattr(e, 'response') and e.response is not None:
                logger.error(redact_secrets(f"Response content: {e.response.content}"))
            break

    return messages


@retry()
def _fetch_media(url, params):
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _extract_captions(posts, max_posts):
    messages = []
    for post in posts:
        if post.get('caption'):
            messages.append(make_head(post['caption']))
            max_posts -= 1
            if max_posts == 0:
                break
    return messages, max_posts
