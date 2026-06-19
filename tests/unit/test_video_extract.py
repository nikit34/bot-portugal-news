from src.parsers.rss.video import extract_video_url


def test_media_content_video_by_medium():
    entry = {'media_content': [{'url': 'https://x/clip', 'medium': 'video'}]}
    assert extract_video_url(entry) == 'https://x/clip'


def test_media_content_video_by_type():
    entry = {'media_content': [{'url': 'https://x/a', 'type': 'video/mp4'}]}
    assert extract_video_url(entry) == 'https://x/a'


def test_media_content_video_by_extension_with_query():
    entry = {'media_content': [{'url': 'https://x/goal.mp4?token=abc'}]}
    assert extract_video_url(entry) == 'https://x/goal.mp4?token=abc'


def test_enclosure_video():
    entry = {'enclosures': [{'url': 'https://x/v.mov', 'type': 'video/quicktime'}]}
    assert extract_video_url(entry) == 'https://x/v.mov'


def test_link_enclosure_video():
    entry = {'links': [
        {'rel': 'alternate', 'href': 'https://x/page'},
        {'rel': 'enclosure', 'href': 'https://x/v.mp4', 'type': 'video/mp4'},
    ]}
    assert extract_video_url(entry) == 'https://x/v.mp4'


def test_image_only_entry_returns_empty():
    entry = {
        'media_content': [{'url': 'https://x/pic.jpg', 'medium': 'image', 'type': 'image/jpeg'}],
        'media_thumbnail': [{'url': 'https://x/thumb.jpg'}],
    }
    assert extract_video_url(entry) == ''


def test_streaming_manifest_not_treated_as_direct_video():
    # HLS/DASH манифесты — не один файл, без ffmpeg не склеить → не берём
    entry = {'media_content': [{'url': 'https://x/master.m3u8'}]}
    assert extract_video_url(entry) == ''


def test_empty_entry():
    assert extract_video_url({}) == ''
