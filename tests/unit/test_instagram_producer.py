import os

import pytest
from PIL import Image

import src.producers.instagram.producer as ig


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeGraph:
    access_token = 'tok'


@pytest.fixture
def context():
    return {'self_instagram_channel': '17841400000000000'}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(_seconds):
        return None
    monkeypatch.setattr(ig.asyncio, 'sleep', _instant)


@pytest.fixture(autouse=True)
def _stories_off(monkeypatch):
    # Feed/comment tests assume no extra Story publish; story tests opt in explicitly.
    monkeypatch.setattr(ig, 'INSTAGRAM_STORIES_ENABLED', False)


async def test_publishes_only_after_container_is_finished(monkeypatch, context):
    # Container reports IN_PROGRESS twice, then FINISHED. /media_publish must not
    # be called until FINISHED — this is the regression for 9007 "media not ready".
    statuses = iter(['IN_PROGRESS', 'IN_PROGRESS', 'FINISHED'])
    publish_calls = []

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'id': 'CONTAINER_1'})
        if url.endswith('/media_publish'):
            publish_calls.append(data)
            return _FakeResponse({'id': 'POST_1'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        assert url.endswith('/CONTAINER_1')
        # publish must not have happened before the container is ready
        assert publish_calls == []
        return _FakeResponse({'status_code': next(statuses)})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    result = await ig.instagram_send_message(_FakeGraph(), 'caption', '', {'url': 'http://img'}, context)

    assert result == {'id': 'POST_1'}
    assert len(publish_calls) == 1
    assert publish_calls[0]['creation_id'] == 'CONTAINER_1'


async def test_raises_on_error_status_without_publishing(monkeypatch, context):
    publish_calls = []

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'id': 'CONTAINER_2'})
        if url.endswith('/media_publish'):
            publish_calls.append(data)
            return _FakeResponse({'id': 'POST_2'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'ERROR'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    with pytest.raises(RuntimeError):
        await ig._wait_until_ready('tok', 'CONTAINER_2')

    assert publish_calls == []


async def test_times_out_when_never_finished(monkeypatch, context):
    monkeypatch.setattr(ig, 'INSTAGRAM_MEDIA_POLL_ATTEMPTS', 3)

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'IN_PROGRESS'})

    monkeypatch.setattr(ig.requests, 'get', fake_get)

    with pytest.raises(RuntimeError, match='not ready'):
        await ig._wait_until_ready('tok', 'CONTAINER_3')


async def test_video_published_as_reel_via_resumable_upload(monkeypatch, tmp_path, context):
    # .mp4 path => REELS resumable upload: create container, upload bytes to
    # rupload, wait FINISHED, then publish. No public image_url involved.
    video = tmp_path / 'clip.mp4'
    video.write_bytes(b'fake-mp4-bytes')

    posts = []

    def fake_post(url, data=None, headers=None, **kwargs):
        posts.append({'url': url, 'data': data, 'headers': headers})
        if url.endswith('/media'):
            assert data['media_type'] == 'REELS'
            assert data['upload_type'] == 'resumable'
            return _FakeResponse({'id': 'REEL_1'})
        if url.startswith('https://rupload.facebook.com/'):
            assert url.endswith('/REEL_1')
            assert headers['Authorization'] == 'OAuth tok'
            assert headers['file_size'] == str(len(b'fake-mp4-bytes'))
            assert data == b'fake-mp4-bytes'
            return _FakeResponse({'success': True})
        if url.endswith('/media_publish'):
            assert data['creation_id'] == 'REEL_1'
            return _FakeResponse({'id': 'REEL_POST_1'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'FINISHED'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    url_path = {'url': object(), 'path': str(video)}  # url is a non-str Telegram media obj
    result = await ig.instagram_send_message(_FakeGraph(), 'caption #x', '', url_path, context)

    assert result == {'id': 'REEL_POST_1'}
    # ensure the photo image_url path was NOT used for a video
    assert all('image_url' not in (p['data'] or {}) for p in posts if isinstance(p['data'], dict))
    # ordering: container -> upload bytes -> publish
    assert posts[0]['url'].endswith('/media')
    assert posts[1]['url'].startswith('https://rupload.facebook.com/')
    assert posts[2]['url'].endswith('/media_publish')


async def test_posts_hashtags_as_first_comment(monkeypatch, context):
    comments = []

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'id': 'C1'})
        if url.endswith('/media_publish'):
            return _FakeResponse({'id': 'MEDIA_1'})
        if url.endswith('/MEDIA_1/comments'):
            comments.append(data)
            return _FakeResponse({'id': 'COMMENT_1'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'FINISHED'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    result = await ig.instagram_send_message(
        _FakeGraph(), 'clean caption', '#benfica #golo', {'url': 'http://img'}, context)

    assert result == {'id': 'MEDIA_1'}
    assert len(comments) == 1
    assert comments[0]['message'] == '#benfica #golo'


async def test_first_comment_failure_does_not_break_publish(monkeypatch, context):
    # The post is already live; a failing first comment (e.g. missing permission)
    # must be swallowed, not re-raised — otherwise @async_retry republishes a dup.
    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            return _FakeResponse({'id': 'C2'})
        if url.endswith('/media_publish'):
            return _FakeResponse({'id': 'MEDIA_2'})
        if url.endswith('/comments'):
            raise Exception('(#10) permission instagram_manage_comments missing')
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'FINISHED'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    result = await ig.instagram_send_message(
        _FakeGraph(), 'caption', '#x', {'url': 'http://img'}, context)

    assert result == {'id': 'MEDIA_2'}


async def test_telegram_photo_minted_via_fb_cdn(monkeypatch, tmp_path, context):
    # Telegram photo has no public url (url is a Telethon object). We mint one by
    # uploading it to the FB Page as an unpublished photo, read its CDN source,
    # publish to IG with that image_url, then delete the temp FB photo.
    photo = tmp_path / 'photo.jpg'
    photo.write_bytes(b'jpeg-bytes')

    put_photo_kwargs = {}
    deleted = []

    class _Graph:
        access_token = 'tok'

        def put_photo(self, image=None, published=None, **kw):
            put_photo_kwargs['published'] = published
            return {'id': 'FBPHOTO_1'}

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/FBPHOTO_1'):
            assert params['fields'] == 'images'
            return _FakeResponse({'images': [{'source': 'https://scontent.fbcdn.net/x.jpg'}]})
        return _FakeResponse({'status_code': 'FINISHED'})  # IG container poll

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            assert data['image_url'] == 'https://scontent.fbcdn.net/x.jpg'
            return _FakeResponse({'id': 'CONT_1'})
        if url.endswith('/media_publish'):
            return _FakeResponse({'id': 'IGMEDIA_1'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_delete(url, params=None, **kwargs):
        deleted.append(url)
        return _FakeResponse({'success': True})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)
    monkeypatch.setattr(ig.requests, 'delete', fake_delete)

    url_path = {'url': object(), 'path': str(photo)}  # non-str url => mint via FB CDN
    result = await ig.instagram_send_message(_Graph(), 'caption', '', url_path, context)

    assert result == {'id': 'IGMEDIA_1'}
    assert put_photo_kwargs['published'] is False
    assert any(u.endswith('/FBPHOTO_1') for u in deleted)  # temp FB photo cleaned up


async def test_image_story_published_after_feed(monkeypatch, context):
    monkeypatch.setattr(ig, 'INSTAGRAM_STORIES_ENABLED', True)
    stories_created = []
    publishes = []

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            if data.get('media_type') == 'STORIES':
                stories_created.append(data)
                return _FakeResponse({'id': 'STORY_CONT'})
            return _FakeResponse({'id': 'FEED_CONT'})
        if url.endswith('/media_publish'):
            publishes.append(data['creation_id'])
            return _FakeResponse({'id': data['creation_id'] + '_PUB'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'FINISHED'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    result = await ig.instagram_send_message(_FakeGraph(), 'caption', '', {'url': 'http://img'}, context)

    assert result == {'id': 'FEED_CONT_PUB'}            # feed result unchanged
    assert len(stories_created) == 1
    assert stories_created[0]['image_url'] == 'http://img'   # reuses the same URL
    assert publishes == ['FEED_CONT', 'STORY_CONT']     # feed first, then story


async def test_video_story_published_after_reel(monkeypatch, tmp_path, context):
    monkeypatch.setattr(ig, 'INSTAGRAM_STORIES_ENABLED', True)
    video = tmp_path / 'clip.mp4'
    video.write_bytes(b'mp4')
    media_types = []
    uploads = []
    publishes = []

    def fake_post(url, data=None, headers=None, **kwargs):
        if url.endswith('/media'):
            media_types.append(data.get('media_type'))
            return _FakeResponse({'id': data['media_type'] + '_CONT'})
        if url.startswith('https://rupload.facebook.com/'):
            uploads.append(url)
            return _FakeResponse({'success': True})
        if url.endswith('/media_publish'):
            publishes.append(data['creation_id'])
            return _FakeResponse({'id': data['creation_id'] + '_PUB'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'FINISHED'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    url_path = {'url': object(), 'path': str(video)}
    result = await ig.instagram_send_message(_FakeGraph(), 'caption', '', url_path, context)

    assert result == {'id': 'REELS_CONT_PUB'}
    assert media_types == ['REELS', 'STORIES']          # feed Reel, then Story
    assert len(uploads) == 2                            # bytes uploaded for both
    assert publishes == ['REELS_CONT', 'STORIES_CONT']


async def test_image_story_uses_overlaid_url(monkeypatch, tmp_path, context):
    # With a real local image and the overlay on, the IG Story is published from a
    # SEPARATE minted url (headline burned in) — the feed keeps the clean photo —
    # and the temp overlay photo + file are cleaned up afterwards.
    monkeypatch.setattr(ig, 'INSTAGRAM_STORIES_ENABLED', True)
    photo = tmp_path / 'p.png'
    Image.new('RGB', (1200, 800), (30, 100, 50)).save(photo)

    deleted = []
    stories_created = []

    class _Graph:
        access_token = 'tok'

        def put_photo(self, image=None, published=None, **kw):
            assert published is False        # overlay minted as unpublished
            return {'id': 'STORYPHOTO_1'}

    def fake_get(url, params=None, **kwargs):
        if url.endswith('/STORYPHOTO_1'):
            return _FakeResponse({'images': [{'source': 'https://cdn/overlay.jpg'}]})
        return _FakeResponse({'status_code': 'FINISHED'})  # container polls

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            if data.get('media_type') == 'STORIES':
                stories_created.append(data)
                return _FakeResponse({'id': 'STORY_CONT'})
            return _FakeResponse({'id': 'FEED_CONT'})
        if url.endswith('/media_publish'):
            return _FakeResponse({'id': data['creation_id'] + '_PUB'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_delete(url, params=None, **kwargs):
        deleted.append(url)
        return _FakeResponse({'success': True})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)
    monkeypatch.setattr(ig.requests, 'delete', fake_delete)

    url_path = {'url': 'http://img', 'path': str(photo)}  # public feed url + local file
    result = await ig.instagram_send_message(_Graph(), 'Benfica vence o Porto', '', url_path, context)

    assert result == {'id': 'FEED_CONT_PUB'}                          # feed unchanged
    assert len(stories_created) == 1
    assert stories_created[0]['image_url'] == 'https://cdn/overlay.jpg'  # story used overlay
    assert any(u.endswith('/STORYPHOTO_1') for u in deleted)          # temp overlay photo cleaned
    assert not os.path.exists(os.path.splitext(str(photo))[0] + '.story.jpg')  # temp file cleaned


async def test_story_gate_suppresses_story(monkeypatch, context):
    # publish_story=False => no STORIES container is created even with stories on.
    monkeypatch.setattr(ig, 'INSTAGRAM_STORIES_ENABLED', True)
    media_types = []

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            media_types.append(data.get('media_type'))
            return _FakeResponse({'id': 'FEED_CONT'})
        if url.endswith('/media_publish'):
            return _FakeResponse({'id': 'FEED_MEDIA'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'FINISHED'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    result = await ig.instagram_send_message(
        _FakeGraph(), 'caption', '', {'url': 'http://img'}, context, publish_story=False)

    assert result == {'id': 'FEED_MEDIA'}
    assert media_types == [None]  # only the feed container, no STORIES container


async def test_story_failure_does_not_break_feed(monkeypatch, context):
    monkeypatch.setattr(ig, 'INSTAGRAM_STORIES_ENABLED', True)

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/media'):
            if data.get('media_type') == 'STORIES':
                raise Exception('story rate limit')
            return _FakeResponse({'id': 'FEED_CONT'})
        if url.endswith('/media_publish'):
            return _FakeResponse({'id': 'FEED_MEDIA'})
        raise AssertionError(f'unexpected POST {url}')

    def fake_get(url, params=None, **kwargs):
        return _FakeResponse({'status_code': 'FINISHED'})

    monkeypatch.setattr(ig.requests, 'post', fake_post)
    monkeypatch.setattr(ig.requests, 'get', fake_get)

    result = await ig.instagram_send_message(_FakeGraph(), 'caption', '', {'url': 'http://img'}, context)

    assert result == {'id': 'FEED_MEDIA'}  # feed publish still succeeds despite story failure
