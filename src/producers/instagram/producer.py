import asyncio
import os
import requests
import logging

from src.producers.repeater import async_retry, retry
from src.producers.text_editor import trunc_str
from src.producers.hashtags import extract_hashtags, append_hashtags, hashtags_line
from src.static.settings import (
    INSTAGRAM_MAX_LENGTH_MESSAGE,
    INSTAGRAM_MEDIA_POLL_ATTEMPTS,
    INSTAGRAM_MEDIA_POLL_INTERVAL,
    INSTAGRAM_VIDEO_POLL_ATTEMPTS,
    INSTAGRAM_VIDEO_POLL_INTERVAL,
    INSTAGRAM_HASHTAGS_AS_COMMENT,
    INSTAGRAM_STORIES_ENABLED,
)

logger = logging.getLogger('app')

# Per-run counters for the debug-chat summary: these failures are best-effort and
# only logged as WARNING otherwise, so they'd silently degrade reach without it.
comment_failures = 0
story_failures = 0


def get_failure_counts():
    return {'comment': comment_failures, 'story': story_failures}


async def _upload_media(access_token, message, media_url, context):
    upload_url = 'https://graph.facebook.com/v18.0/' + context['self_instagram_channel'] + '/media'
    data = {
        'image_url': media_url,
        'caption': message,
        'access_token': access_token,
    }
    response = await asyncio.to_thread(requests.post, upload_url, data=data)
    response.raise_for_status()
    return response.json().get('id')


async def _wait_until_ready(access_token, media_id, attempts=None, interval=None):
    # Meta скачивает/транскодирует медиа асинхронно. Опрашиваем status_code
    # контейнера, пока он не станет FINISHED, и только тогда публикуем — иначе
    # /media_publish падает с 9007/2207027 "media not ready". ERROR/EXPIRED —
    # терминальные, ретраить тот же контейнер бессмысленно. Бюджет ожидания
    # параметризуем (картинки vs видео), по умолчанию — для картинок.
    attempts = INSTAGRAM_MEDIA_POLL_ATTEMPTS if attempts is None else attempts
    interval = INSTAGRAM_MEDIA_POLL_INTERVAL if interval is None else interval
    status_url = 'https://graph.facebook.com/v18.0/' + media_id
    params = {'fields': 'status_code', 'access_token': access_token}
    status_code = None
    for _ in range(attempts):
        response = await asyncio.to_thread(requests.get, status_url, params=params)
        response.raise_for_status()
        status_code = response.json().get('status_code')
        if status_code == 'FINISHED':
            return
        if status_code in ('ERROR', 'EXPIRED'):
            raise RuntimeError(
                f"Instagram media {media_id} processing failed: status_code={status_code}")
        await asyncio.sleep(interval)
    raise RuntimeError(
        f"Instagram media {media_id} not ready after "
        f"{attempts} attempts (last status_code={status_code})")


async def _upload_reel(access_token, caption, file_path, context):
    # Видео нельзя отдать IG как локальный файл напрямую (в отличие от FB /videos)
    # и публичного URL у нас нет (файл скачан из Telegram). Используем resumable
    # upload: создаём контейнер REELS и заливаем байты на rupload.facebook.com.
    container_id = await _create_reel_container(access_token, caption, context)
    await _upload_reel_bytes(access_token, container_id, file_path)
    return container_id


async def _create_reel_container(access_token, caption, context):
    url = 'https://graph.facebook.com/v18.0/' + context['self_instagram_channel'] + '/media'
    data = {
        'media_type': 'REELS',
        'upload_type': 'resumable',
        'caption': caption,
        # дублируем Reel в основную ленту/сетку профиля, а не только во вкладку Reels
        'share_to_feed': 'true',
        'access_token': access_token,
    }
    response = await asyncio.to_thread(requests.post, url, data=data)
    response.raise_for_status()
    return response.json().get('id')


async def _upload_reel_bytes(access_token, container_id, file_path):
    upload_url = 'https://rupload.facebook.com/ig-api-upload/v18.0/' + container_id
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


async def _publish_media(access_token, media_id, context):
    publish_url = 'https://graph.facebook.com/v18.0/' + context['self_instagram_channel'] + '/media_publish'
    params = {
        'creation_id': media_id,
        'access_token': access_token
    }
    response = await asyncio.to_thread(requests.post, publish_url, data=params)
    response.raise_for_status()
    return response.json()


async def _mint_image_url(graph, file_path):
    # IG не принимает локальные байты картинки — только публичный image_url. У фото
    # из Telegram такого URL нет, поэтому "чеканим" его: грузим фото на FB-страницу
    # как НЕопубликованное (published=false, в ленте не появляется) и читаем CDN-
    # ссылку рендера. После публикации в IG временное фото удаляем (_delete_photo).
    photo_id = await asyncio.to_thread(_upload_unpublished_photo, graph, file_path)
    source = await _get_photo_source(graph.access_token, photo_id)
    return source, photo_id


def _upload_unpublished_photo(graph, file_path):
    with open(file_path, 'rb') as media_file:
        result = graph.put_photo(image=media_file, published=False)
    return result.get('id')


async def _get_photo_source(access_token, photo_id):
    url = 'https://graph.facebook.com/v18.0/' + photo_id
    params = {'fields': 'images', 'access_token': access_token}
    response = await asyncio.to_thread(requests.get, url, params=params)
    response.raise_for_status()
    images = response.json().get('images') or []
    if not images:
        raise RuntimeError(f"FB photo {photo_id}: no image renditions to mint IG image_url")
    return images[0]['source']  # FB отдаёт рендеры от большего к меньшему


async def _delete_photo(access_token, photo_id):
    # Уборка временного FB-фото — best-effort: IG к этому моменту уже забрал себе
    # копию картинки, а провал удаления не должен ронять успешную публикацию.
    if not photo_id:
        return
    url = 'https://graph.facebook.com/v18.0/' + photo_id
    try:
        response = await asyncio.to_thread(
            requests.delete, url, params={'access_token': access_token})
        response.raise_for_status()
    except Exception as e:
        logger.warning(f"[instagram] failed to delete temp FB photo {photo_id}: {e}")


async def _publish_story(access_token, story, context):
    # Дублируем пост в Stories тем же медиа. Best-effort: пост уже в ленте, поэтому
    # ошибку Stories НЕ пробрасываем — иначе @async_retry перевыложит ленту дублем.
    kind, payload = story
    try:
        if kind == 'video':
            container_id = await _create_story_video_container(access_token, context)
            await _upload_reel_bytes(access_token, container_id, payload)
            await _wait_until_ready(
                access_token, container_id, INSTAGRAM_VIDEO_POLL_ATTEMPTS, INSTAGRAM_VIDEO_POLL_INTERVAL)
        else:
            container_id = await _create_story_image_container(access_token, payload, context)
            await _wait_until_ready(access_token, container_id)
        await _publish_media(access_token, container_id, context)
        logger.info("[instagram] story published")
    except Exception as e:
        global story_failures
        story_failures += 1
        logger.warning(f"[instagram] story publish failed: {e}")


async def _create_story_image_container(access_token, image_url, context):
    url = 'https://graph.facebook.com/v18.0/' + context['self_instagram_channel'] + '/media'
    data = {'media_type': 'STORIES', 'image_url': image_url, 'access_token': access_token}
    response = await asyncio.to_thread(requests.post, url, data=data)
    response.raise_for_status()
    return response.json().get('id')


async def _create_story_video_container(access_token, context):
    url = 'https://graph.facebook.com/v18.0/' + context['self_instagram_channel'] + '/media'
    data = {'media_type': 'STORIES', 'upload_type': 'resumable', 'access_token': access_token}
    response = await asyncio.to_thread(requests.post, url, data=data)
    response.raise_for_status()
    return response.json().get('id')


async def _post_first_comment(access_token, media_id, comment):
    # Best-effort: пост уже опубликован, поэтому ошибку комментария НЕ пробрасываем —
    # иначе @async_retry перезапустит всю публикацию и создаст дубль. Просто WARNING.
    if not comment or not media_id:
        return
    url = 'https://graph.facebook.com/v18.0/' + media_id + '/comments'
    data = {'message': comment, 'access_token': access_token}
    try:
        response = await asyncio.to_thread(requests.post, url, data=data)
        response.raise_for_status()
    except Exception as e:
        global comment_failures
        comment_failures += 1
        logger.warning(f"[instagram] first comment failed for media {media_id}: {e}")


def _is_video_file(file_path):
    return bool(file_path) and file_path.lower().endswith('.mp4')


@retry()
def instagram_prepare_post(translated_message, doc):
    # Хэштеги на IG — основной канал органического обнаружения поста. Метки те же,
    # что и для Facebook (общий extract_hashtags). Возвращаем (подпись, комментарий):
    # по умолчанию подпись чистая, а хэштеги уходят первым комментарием; при
    # INSTAGRAM_HASHTAGS_AS_COMMENT=False — хэштеги в подписи, комментарий пустой.
    text = trunc_str(translated_message, INSTAGRAM_MAX_LENGTH_MESSAGE)
    keywords = extract_hashtags(doc)
    if INSTAGRAM_HASHTAGS_AS_COMMENT:
        return text, hashtags_line(keywords)
    return append_hashtags(text, keywords), ''


@async_retry()
async def instagram_send_message(graph, message, comment, url_path, context):
    access_token = graph.access_token
    file_path = url_path.get('path')
    temp_photo_id = None
    if _is_video_file(file_path):
        media_id = await _upload_reel(access_token, message, file_path, context)
        await _wait_until_ready(
            access_token, media_id, INSTAGRAM_VIDEO_POLL_ATTEMPTS, INSTAGRAM_VIDEO_POLL_INTERVAL)
        story = ('video', file_path)
    else:
        media_url = url_path.get('url')
        if not isinstance(media_url, str):
            # нет публичного URL (фото из Telegram) — чеканим его через FB CDN
            media_url, temp_photo_id = await _mint_image_url(graph, file_path)
        media_id = await _upload_media(access_token, message, media_url, context)
        await _wait_until_ready(access_token, media_id)
        story = ('image', media_url)  # переиспользуем тот же URL для Stories
    result = await _publish_media(access_token, media_id, context)
    await _post_first_comment(access_token, result.get('id'), comment)
    if INSTAGRAM_STORIES_ENABLED:
        await _publish_story(access_token, story, context)
    await _delete_photo(access_token, temp_photo_id)
    return result
