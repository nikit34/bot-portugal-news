import requests
from src.producers.repeater import retry
from src.processor.history_comparator import make_head
from src.static.settings import GRAPH_API_BASE
import logging

logger = logging.getLogger(__name__)


def get_facebook_published_messages(graph, context, max_posts):
    url = GRAPH_API_BASE + context['self_facebook_page_id'] + "/posts"
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
            # Pagination can't continue without this page, so we stop with a partial
            # history. Warn loudly: an incomplete FB history weakens dedup and risks
            # re-posting to FB (mitigated by TG/IG histories also feeding dedup).
            logger.error(f"Error fetching Facebook posts: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.content}")
            logger.warning(
                f"[facebook] history INCOMPLETE — only {len(messages)} posts read before error; "
                f"dedup may be weaker this run")
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
            messages.append(make_head(post['message']))
            max_posts -= 1
            if max_posts == 0:
                break
    return messages, max_posts
