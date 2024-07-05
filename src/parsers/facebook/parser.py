import requests
from src.producers.repeater import retry
from src.static.settings import KEY_SEARCH_LENGTH_CHARS
from src.static.sources import self_facebook_page_id


def get_published_messages(graph, max_posts):
    url = "https://graph.facebook.com/v20.0/" + self_facebook_page_id + "/posts"
    params = {
        'access_token': graph.access_token,
        'limit': 50
    }

    messages = []

    while max_posts > 0:
        data = _fetch_posts(url, params)
        posts = data.get('data', [])

        new_messages, max_posts = _extract_messages(posts, max_posts)
        messages.extend(new_messages)

        if 'paging' in data and 'next' in data['paging']:
            url = data['paging']['next']
            params = {}
        else:
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
            head = post['message'][:KEY_SEARCH_LENGTH_CHARS].strip()
            messages.append(head)
            max_posts -= 1
            if max_posts == 0:
                break
    return messages, max_posts
