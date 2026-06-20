import os

import pytest
from PIL import Image

import src.producers.facebook.producer as fb


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeGraph:
    access_token = 'tok'

    def __init__(self):
        self.put_photo_calls = []

    def put_photo(self, image=None, message=None, published=None, **kw):
        self.put_photo_calls.append({'message': message, 'published': published})
        # mimic the facebook SDK: feed photo carries a post_id, both carry an id
        return {'id': 'FBPHOTO_1', 'post_id': 'PAGE_POST_1'}


@pytest.fixture
def context():
    return {'self_facebook_page_id': '1234567890'}


@pytest.fixture(autouse=True)
def _reset_counter():
    # The failure counter is a module global; isolate tests from each other.
    fb.story_failures = 0
    yield
    fb.story_failures = 0


@pytest.fixture(autouse=True)
def _stories_off(monkeypatch):
    # Feed tests assume no extra Story publish; story tests opt in explicitly.
    monkeypatch.setattr(fb, 'FACEBOOK_STORIES_ENABLED', False)


async def test_photo_feed_post_returns_put_photo_result(monkeypatch, tmp_path, context):
    photo = tmp_path / 'p.jpg'
    photo.write_bytes(b'jpeg')
    graph = _FakeGraph()

    def fake_post(url, **kwargs):
        raise AssertionError('no HTTP POST expected for a plain photo feed post')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    result = await fb.facebook_send_message(graph, 'hello', {'path': str(photo)}, context)

    assert result == {'id': 'FBPHOTO_1', 'post_id': 'PAGE_POST_1'}
    assert graph.put_photo_calls == [{'message': 'hello', 'published': None}]


async def test_photo_story_published_after_feed(monkeypatch, tmp_path, context):
    monkeypatch.setattr(fb, 'FACEBOOK_STORIES_ENABLED', True)
    photo = tmp_path / 'p.jpg'
    photo.write_bytes(b'jpeg')
    graph = _FakeGraph()
    posts = []

    def fake_post(url, data=None, **kwargs):
        posts.append({'url': url, 'data': data})
        if url.endswith('/photo_stories'):
            return _FakeResponse({'success': True, 'post_id': 'STORY_POST_1'})
        raise AssertionError(f'unexpected POST {url}')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    result = await fb.facebook_send_message(graph, 'hello', {'path': str(photo)}, context)

    assert result == {'id': 'FBPHOTO_1', 'post_id': 'PAGE_POST_1'}  # feed result unchanged
    # photo uploaded twice: published feed photo, then an unpublished one for the story
    assert [c['published'] for c in graph.put_photo_calls] == [None, False]
    assert len(posts) == 1
    assert posts[0]['url'].endswith('/1234567890/photo_stories')
    assert posts[0]['data']['photo_id'] == 'FBPHOTO_1'
    assert fb.story_failures == 0


async def test_video_feed_and_story_resumable_upload(monkeypatch, tmp_path, context):
    monkeypatch.setattr(fb, 'FACEBOOK_STORIES_ENABLED', True)
    video = tmp_path / 'clip.mp4'
    video.write_bytes(b'fake-mp4-bytes')
    graph = _FakeGraph()
    posts = []

    def fake_post(url, data=None, files=None, headers=None, **kwargs):
        posts.append({'url': url, 'data': data, 'headers': headers})
        if url.endswith('/videos'):                       # feed video
            return _FakeResponse({'id': 'FEED_VIDEO_1'})
        if url.endswith('/video_stories'):
            if data.get('upload_phase') == 'start':
                return _FakeResponse(
                    {'video_id': 'STORY_VID_1',
                     'upload_url': 'https://rupload.facebook.com/video-upload/v18.0/STORY_VID_1'})
            if data.get('upload_phase') == 'finish':
                assert data['video_id'] == 'STORY_VID_1'
                return _FakeResponse({'success': True, 'post_id': 'STORY_POST_2'})
        if url.startswith('https://rupload.facebook.com/'):
            assert headers['Authorization'] == 'OAuth tok'
            assert headers['file_size'] == str(len(b'fake-mp4-bytes'))
            return _FakeResponse({'success': True})
        raise AssertionError(f'unexpected POST {url}')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    result = await fb.facebook_send_message(graph, 'desc', {'path': str(video)}, context)

    assert result == {'id': 'FEED_VIDEO_1'}              # feed result unchanged
    # ordering: feed video -> story start -> upload bytes -> story finish
    assert posts[0]['url'].endswith('/videos')
    assert posts[1]['data']['upload_phase'] == 'start'
    assert posts[2]['url'].startswith('https://rupload.facebook.com/')
    assert posts[3]['data']['upload_phase'] == 'finish'
    assert fb.story_failures == 0


async def test_story_failure_does_not_break_feed(monkeypatch, tmp_path, context):
    # The post is already live; a failing Story (e.g. missing permission / rate
    # limit) must be swallowed, not re-raised — otherwise @async_retry republishes.
    monkeypatch.setattr(fb, 'FACEBOOK_STORIES_ENABLED', True)
    photo = tmp_path / 'p.jpg'
    photo.write_bytes(b'jpeg')
    graph = _FakeGraph()

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/photo_stories'):
            raise Exception('(#200) permission to publish a story missing')
        raise AssertionError(f'unexpected POST {url}')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    result = await fb.facebook_send_message(graph, 'hello', {'path': str(photo)}, context)

    assert result == {'id': 'FBPHOTO_1', 'post_id': 'PAGE_POST_1'}  # feed still succeeds
    assert fb.story_failures == 1
    assert fb.get_failure_counts() == {'fb_story': 1}


async def test_photo_story_burns_headline_into_overlay(monkeypatch, tmp_path, context):
    # With a real image and the overlay on, the Story uploads the rendered 9:16
    # image (headline burned in), not the original photo — and cleans it up after.
    monkeypatch.setattr(fb, 'FACEBOOK_STORIES_ENABLED', True)
    photo = tmp_path / 'p.png'
    Image.new('RGB', (1200, 800), (30, 100, 50)).save(photo)
    graph = _FakeGraph()

    uploaded = []

    def fake_upload(_graph, path):
        uploaded.append(path)
        return 'FBPHOTO_1'

    monkeypatch.setattr(fb, '_upload_unpublished_photo', fake_upload)

    def fake_post(url, data=None, **kwargs):
        if url.endswith('/photo_stories'):
            return _FakeResponse({'success': True})
        raise AssertionError(f'unexpected POST {url}')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    result = await fb.facebook_send_message(
        graph, 'Benfica vence o Porto por 2-1 no classico', {'path': str(photo)}, context)

    assert result == {'id': 'FBPHOTO_1', 'post_id': 'PAGE_POST_1'}  # feed unchanged
    assert len(uploaded) == 1
    assert uploaded[0].endswith('.story.jpg')      # overlay image, not the original
    assert not os.path.exists(uploaded[0])         # temp overlay cleaned up
    assert fb.story_failures == 0


async def test_photo_story_falls_back_to_original_when_overlay_fails(monkeypatch, tmp_path, context):
    # Overlay render failure must NOT skip the Story — it falls back to the original
    # media and the story still publishes (best-effort, no failure recorded).
    monkeypatch.setattr(fb, 'FACEBOOK_STORIES_ENABLED', True)
    photo = tmp_path / 'p.jpg'
    photo.write_bytes(b'not-an-image')               # unreadable => overlay returns None
    graph = _FakeGraph()
    posts = []

    def fake_post(url, data=None, **kwargs):
        posts.append(url)
        if url.endswith('/photo_stories'):
            return _FakeResponse({'success': True})
        raise AssertionError(f'unexpected POST {url}')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    await fb.facebook_send_message(graph, 'hello', {'path': str(photo)}, context)

    # original photo uploaded unpublished for the story; story published; no overlay file
    assert [c['published'] for c in graph.put_photo_calls] == [None, False]
    assert posts and posts[0].endswith('/photo_stories')
    assert fb.story_failures == 0
    assert not os.path.exists(os.path.splitext(str(photo))[0] + '.story.jpg')


async def test_no_story_when_gate_suppresses(monkeypatch, tmp_path, context):
    # Story-gate: publish_story=False suppresses the Story even with stories enabled.
    monkeypatch.setattr(fb, 'FACEBOOK_STORIES_ENABLED', True)
    photo = tmp_path / 'p.jpg'
    photo.write_bytes(b'jpeg')
    graph = _FakeGraph()

    def fake_post(url, **kwargs):
        raise AssertionError('no Story POST expected when the gate suppresses it')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    await fb.facebook_send_message(graph, 'hello', {'path': str(photo)}, context, publish_story=False)

    assert len(graph.put_photo_calls) == 1  # only the feed photo


async def test_no_story_when_disabled(monkeypatch, tmp_path, context):
    # _stories_off fixture keeps FACEBOOK_STORIES_ENABLED False.
    photo = tmp_path / 'p.jpg'
    photo.write_bytes(b'jpeg')
    graph = _FakeGraph()

    def fake_post(url, **kwargs):
        raise AssertionError('no Story POST expected when stories are disabled')

    monkeypatch.setattr(fb.requests, 'post', fake_post)

    await fb.facebook_send_message(graph, 'hello', {'path': str(photo)}, context)

    assert len(graph.put_photo_calls) == 1  # only the feed photo, no unpublished story upload
