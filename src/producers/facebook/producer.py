import pyshorteners
import requests
from collections import Counter

from src.producers.repeater import retry, async_retry
from src.static.settings import FACEBOOK_MAX_LENGTH_MESSAGE, WEIGHT_KEYWORDS_THRESHOLD, MAX_COUNT_KEYWORDS
from src.static.sources import self_facebook_page_id
from src.producers.text_editor import trunc_str


@retry()
def facebook_prepare_post(nlp, translated_message, link):
    shortener = pyshorteners.Shortener()
    shorted_link = shortener.tinyurl.short(link)
    text_link = trunc_str(translated_message, FACEBOOK_MAX_LENGTH_MESSAGE) + '\n\n' + shorted_link
    candidate_keywords = _extract_keywords(nlp, text_link)
    keywords = _processing_keywords(candidate_keywords)
    return _add_keywords_text(text_link, keywords)


@async_retry()
async def facebook_send_message(graph, message, url_path):
    file_path = url_path.get("path")
    if not file_path.lower().endswith(".mp4"):
        return graph.put_photo(image=open(file_path, 'rb'), message=message)
    return _send_video(graph, message, file_path)


def _send_video(graph, message, file_path):
    url = 'https://graph.facebook.com/v20.0/' + self_facebook_page_id + '/videos'

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


def _extract_keywords(nlp, text):
    doc = nlp(text)
    candidate_words = [token.text for token in doc if token.pos_ in ['NOUN', 'PROPN', 'ADJ']]
    named_entities = [ent.text for ent in doc.ents]
    all_keywords = candidate_words + named_entities
    keyword_freq = Counter(all_keywords)
    return keyword_freq.most_common(MAX_COUNT_KEYWORDS)


def _processing_keywords(candidate_keywords):
    keywords = []
    for item in candidate_keywords:
        if item[1] >= WEIGHT_KEYWORDS_THRESHOLD:
            keywords.append(item[0])
    return keywords


def _add_keywords_text(text, keywords):
    return text + '\n' + ' '.join('#' + item for item in keywords)
