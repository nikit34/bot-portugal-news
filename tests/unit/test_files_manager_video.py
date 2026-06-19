import os
import pytest
from unittest.mock import patch

import src.files_manager as fm
from src.files_manager import SaveVideoUrl, VideoSkip
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
