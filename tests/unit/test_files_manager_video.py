import os
import pytest
from unittest.mock import patch

import src.files_manager as fm
from src.files_manager import SaveVideoUrl, SaveYouTubeVideo, VideoSkip
from src.static.sources import tmp_folder


class _FakeStreamResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=None):
        return iter(self._chunks)


# ---- SaveVideoUrl -----------------------------------------------------------

@pytest.mark.asyncio
async def test_save_video_url_success():
    saver = SaveVideoUrl("https://x/clip.mp4")
    with patch('src.files_manager.requests.get',
               return_value=_FakeStreamResponse([b'video-bytes-here'])):
        result = await saver()
    assert result['url'] == "https://x/clip.mp4"
    assert result['path'].startswith(tmp_folder)
    assert result['path'].endswith('.mp4')
    assert os.path.exists(result['path'])
    os.remove(result['path'])


@pytest.mark.asyncio
async def test_save_video_url_size_cap_aborts_and_cleans_up(monkeypatch):
    # cap = 0MB → первый же чанк превышает лимит → VideoSkip, недокачанный файл удалён
    monkeypatch.setattr(fm, 'MAX_VIDEO_SIZE_MB', 0)
    saver = SaveVideoUrl("https://x/huge.mp4")
    captured = {}
    real_open = open

    def tracking_open(path, *a, **k):
        captured['path'] = path
        return real_open(path, *a, **k)

    with patch('src.files_manager.requests.get',
               return_value=_FakeStreamResponse([b'x' * 1024])):
        with patch('builtins.open', side_effect=tracking_open):
            with pytest.raises(VideoSkip):
                await saver()
    assert 'path' in captured
    assert not os.path.exists(captured['path'])  # cleaned up on abort


# ---- SaveYouTubeVideo (yt-dlp mocked) ---------------------------------------

class _FakeYDL:
    """Подменяет yt_dlp.YoutubeDL: extract_info управляется тестом."""
    info = None
    raises = False

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        if _FakeYDL.raises:
            raise RuntimeError("bot check")
        return _FakeYDL.info

    def prepare_filename(self, info):
        return (info or {}).get('_fallback', '')


@pytest.mark.asyncio
async def test_youtube_download_success(tmp_path):
    mp4 = tmp_path / "vid.mp4"
    mp4.write_bytes(b'\x00\x00')
    _FakeYDL.raises = False
    _FakeYDL.info = {'requested_downloads': [{'filepath': str(mp4)}]}
    with patch('yt_dlp.YoutubeDL', _FakeYDL):
        result = await SaveYouTubeVideo("https://youtube.com/watch?v=abc")()
    assert result['path'] == str(mp4)
    assert result['url'] == "https://youtube.com/watch?v=abc"


@pytest.mark.asyncio
async def test_youtube_download_filtered_no_file_raises_skip():
    # match_filter / max_filesize отсёк формат → extract_info вернул None → VideoSkip
    _FakeYDL.raises = False
    _FakeYDL.info = None
    with patch('yt_dlp.YoutubeDL', _FakeYDL):
        with pytest.raises(VideoSkip):
            await SaveYouTubeVideo("https://youtube.com/watch?v=abc")()


@pytest.mark.asyncio
async def test_youtube_download_non_mp4_raises_skip_and_removes(tmp_path):
    webm = tmp_path / "vid.webm"
    webm.write_bytes(b'\x00')
    _FakeYDL.raises = False
    _FakeYDL.info = {'requested_downloads': [{'filepath': str(webm)}]}
    with patch('yt_dlp.YoutubeDL', _FakeYDL):
        with pytest.raises(VideoSkip):
            await SaveYouTubeVideo("https://youtube.com/watch?v=abc")()
    assert not os.path.exists(str(webm))  # non-mp4 removed


@pytest.mark.asyncio
async def test_youtube_download_ytdlp_error_raises_skip():
    _FakeYDL.raises = True
    _FakeYDL.info = None
    with patch('yt_dlp.YoutubeDL', _FakeYDL):
        with pytest.raises(VideoSkip):
            await SaveYouTubeVideo("https://youtube.com/watch?v=abc")()
    _FakeYDL.raises = False
