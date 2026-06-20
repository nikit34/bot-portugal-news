import asyncio
import os
import logging
import requests

from src.producers.repeater import retry, async_retry
from src.static.settings import FACEBOOK_MAX_LENGTH_MESSAGE, FACEBOOK_STORIES_ENABLED, HASHTAG_MAX_FB
from src.producers.text_editor import prepare_body
from src.producers.hashtags import extract_hashtags, append_hashtags
from src.producers.story_overlay import build_story_image, discard_overlay

logger = logging.getLogger('app')

# Per-run counter for the debug-chat summary: Story publishing is best-effort and
# only logged as WARNING otherwise, so it'd silently degrade reach without it.
story_failures = 0


def get_failure_counts():
    return {'fb_story': story_failures}


@retry()
def facebook_prepare_post(translated_message, doc):
    text = prepare_body(translated_message, doc, FACEBOOK_MAX_LENGTH_MESSAGE)
    keywords = extract_hashtags(doc, HASHTAG_MAX_FB)
    return append_hashtags(text, keywords)


@async_retry()
async def facebook_send_message(graph, message, url_path, context, publish_story=True):
    file_path = url_path.get("path")
    is_video = file_path.lower().endswith(".mp4")
    if is_video:
        result = await asyncio.to_thread(_send_video, graph, message, file_path, context)
    else:
        result = await asyncio.to_thread(_send_photo, graph, message, file_path)
    # publish_story=False lets the story-gate suppress the extra Story publish when
    # the IG/FB daily budget is tight (story doesn't reach non-followers anyway).
    if FACEBOOK_STORIES_ENABLED and publish_story:
        await _publish_story(graph, file_path, is_video, context, message)
    return result


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


async def _publish_story(graph, file_path, is_video, context, message=None):
    # Дублируем пост в Stories тем же медиа. Best-effort: пост уже в ленте, поэтому
    # ошибку Stories НЕ пробрасываем — иначе @async_retry перевыложит ленту дублем.
    try:
        if is_video:
            await _publish_video_story(graph, file_path, context)
        else:
            await _publish_photo_story(graph, file_path, context, message)
        logger.info("[facebook] story published")
    except Exception as e:
        global story_failures
        story_failures += 1
        logger.warning(f"[facebook] story publish failed: {e}")


async def _publish_photo_story(graph, file_path, context, message=None):
    # Фото-сторис двухшаговая: сначала грузим фото на страницу НЕопубликованным
    # (published=false, в ленте не появляется), затем публикуем его как Story по id.
    # Если включён оверлей и заголовок прожёгся — грузим картинку с текстом,
    # иначе оригинал (Stories API подпись/текст не принимает, см. story_overlay).
    overlay_path = build_story_image(file_path, message)
    try:
        photo_id = await asyncio.to_thread(
            _upload_unpublished_photo, graph, overlay_path or file_path)
        url = 'https://graph.facebook.com/v18.0/' + context['self_facebook_page_id'] + '/photo_stories'
        data = {'photo_id': photo_id, 'access_token': graph.access_token}
        response = await asyncio.to_thread(requests.post, url, data=data)
        response.raise_for_status()
        return response.json()
    finally:
        discard_overlay(overlay_path)


def _upload_unpublished_photo(graph, file_path):
    with open(file_path, 'rb') as media_file:
        result = graph.put_photo(image=media_file, published=False)
    return result.get('id')


async def _publish_video_story(graph, file_path, context):
    # Видео-сторис — resumable upload: открываем сессию (upload_phase=start),
    # заливаем байты на выданный upload_url, затем завершаем (upload_phase=finish).
    video_id, upload_url = await _start_video_story(graph, context)
    await _upload_video_bytes(graph.access_token, upload_url, file_path)
    return await _finish_video_story(graph, video_id, context)


async def _start_video_story(graph, context):
    url = 'https://graph.facebook.com/v18.0/' + context['self_facebook_page_id'] + '/video_stories'
    data = {'upload_phase': 'start', 'access_token': graph.access_token}
    response = await asyncio.to_thread(requests.post, url, data=data)
    response.raise_for_status()
    payload = response.json()
    return payload.get('video_id'), payload.get('upload_url')


async def _upload_video_bytes(access_token, upload_url, file_path):
    file_size = os.path.getsize(file_path)
    headers = {
        'Authorization': 'OAuth ' + access_token,
        'offset': '0',
        'file_size': str(file_size),
    }

    def _post():
        with open(file_path, 'rb') as media_file:
            return requests.post(upload_url, headers=headers, data=media_file.read())

    response = await asyncio.to_thread(_post)
    response.raise_for_status()
    return response.json()


async def _finish_video_story(graph, video_id, context):
    url = 'https://graph.facebook.com/v18.0/' + context['self_facebook_page_id'] + '/video_stories'
    data = {'upload_phase': 'finish', 'video_id': video_id, 'access_token': graph.access_token}
    response = await asyncio.to_thread(requests.post, url, data=data)
    response.raise_for_status()
    return response.json()
