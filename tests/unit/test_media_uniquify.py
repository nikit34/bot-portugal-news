import os
import types
import pytest
from unittest.mock import patch
from PIL import Image

import src.producers.media_uniquify as mu


# ---- watermark text resolution ---------------------------------------------

def test_handle_from_url():
    assert mu._handle_from_url('https://t.me/sportportugal') == '@sportportugal'
    assert mu._handle_from_url('https://t.me/sportportugal/') == '@sportportugal'
    assert mu._handle_from_url('@already') == '@already'
    assert mu._handle_from_url('') == ''


def test_resolve_watermark_text_from_config(monkeypatch):
    monkeypatch.setattr(mu, 'WATERMARK_TEXT', '')
    ctx = {'self_telegram_channel': 'https://t.me/sportportugal'}
    assert mu.resolve_watermark_text(ctx) == '@sportportugal'


def test_resolve_watermark_text_explicit_override(monkeypatch):
    monkeypatch.setattr(mu, 'WATERMARK_TEXT', 'Futebol PT')
    ctx = {'self_telegram_channel': 'https://t.me/sportportugal'}
    assert mu.resolve_watermark_text(ctx) == 'Futebol PT'


# ---- image uniquify ---------------------------------------------------------

def test_video_vf_includes_resolution_cap(monkeypatch):
    monkeypatch.setattr(mu, 'UNIQUIFY_VIDEO_MAX_DIM', 1280)
    vf = mu._video_vf()
    assert "min(1280,iw)" in vf and "min(1280,ih)" in vf
    assert "force_original_aspect_ratio=decrease" in vf
    # even-dim scale still trails the cap so yuv420p stays happy
    assert vf.strip().endswith("scale=trunc(iw/2)*2:trunc(ih/2)*2")


def test_video_vf_no_cap_when_disabled(monkeypatch):
    monkeypatch.setattr(mu, 'UNIQUIFY_VIDEO_MAX_DIM', 0)
    vf = mu._video_vf()
    assert "force_original_aspect_ratio" not in vf


def _jpeg_with_exif(path):
    exif = Image.Exif()
    exif[0x010e] = "original source description"  # ImageDescription
    Image.new('RGB', (640, 480), (12, 34, 56)).save(path, format='JPEG', exif=exif)


def test_uniquify_image_produces_jpeg_and_strips_exif(tmp_path):
    src = str(tmp_path / 'in.jpg')
    _jpeg_with_exif(src)
    assert len(Image.open(src).getexif()) > 0  # sanity: source has EXIF

    out = mu.uniquify_image(src, '@sportportugal')
    assert out and out.endswith('.uniq.jpg') and os.path.exists(out)
    result = Image.open(out)
    assert result.format == 'JPEG'
    assert len(result.getexif()) == 0          # EXIF stripped
    assert result.size != (640, 480)            # cropped → hash shifts


def test_uniquify_image_draws_watermark(tmp_path):
    src = str(tmp_path / 'flat.jpg')
    Image.new('RGB', (800, 600), (30, 60, 90)).save(src, format='JPEG')  # dark flat bg
    out = mu.uniquify_image(src, '@sportportugal')
    im = Image.open(out).convert('RGB')
    w, h = im.size
    # watermark sits bottom-right: white text is much brighter than the R=30 bg
    wm_pixels = sum(1 for x in range(w * 3 // 5, w) for y in range(h * 4 // 5, h)
                    if im.getpixel((x, y))[0] > 110)
    assert wm_pixels > 100  # channel name burned in


def test_uniquify_image_without_watermark_text(tmp_path):
    src = str(tmp_path / 'in.jpg')
    Image.new('RGB', (500, 500), (200, 10, 10)).save(src, format='JPEG')
    out = mu.uniquify_image(src, '')  # no channel → no watermark, transforms still apply
    assert out and os.path.exists(out)


# ---- apply_uniquify (serve entry point) -------------------------------------

def test_apply_uniquify_image_mutates_url_path(tmp_path):
    src = str(tmp_path / 'orig.jpg')
    Image.new('RGB', (700, 500), (20, 120, 200)).save(src, format='JPEG')
    url_path = {'url': 'https://cdn/source.jpg', 'path': src}

    mu.apply_uniquify(url_path, is_video=False, context={'self_telegram_channel': 'https://t.me/sportportugal'})

    assert url_path['path'] != src
    assert url_path['path'].endswith('.uniq.jpg')
    assert os.path.exists(url_path['path'])
    assert url_path['url'] is None          # forces IG to mint from processed local file
    assert not os.path.exists(src)          # original removed
    os.remove(url_path['path'])


def test_apply_uniquify_disabled_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(mu, 'UNIQUIFY_ENABLED', False)
    src = str(tmp_path / 'orig.jpg')
    Image.new('RGB', (300, 300), (1, 2, 3)).save(src, format='JPEG')
    url_path = {'url': 'u', 'path': src}
    mu.apply_uniquify(url_path, is_video=False, context={})
    assert url_path == {'url': 'u', 'path': src}  # untouched
    assert os.path.exists(src)


# ---- video uniquify (ffmpeg mocked) -----------------------------------------

def _fake_run_success(cmd, **kwargs):
    with open(cmd[-1], 'wb') as f:   # last arg = output path
        f.write(b'\x00\x00fakemp4')
    return types.SimpleNamespace(returncode=0, stderr=b'')


def test_uniquify_video_success_mocked(tmp_path):
    src = str(tmp_path / 'clip.mp4')
    with open(src, 'wb') as f:
        f.write(b'rawvideo')
    with patch.object(mu, '_ffmpeg_exe', return_value='ffmpeg'), \
         patch.object(mu.subprocess, 'run', side_effect=_fake_run_success):
        out = mu.uniquify_video(src, '')   # empty wm → -vf path, no png
    assert out and out.endswith('.uniq.mp4') and os.path.exists(out)


def test_uniquify_video_ffmpeg_failure_returns_none(tmp_path):
    src = str(tmp_path / 'clip.mp4')
    with open(src, 'wb') as f:
        f.write(b'rawvideo')

    def fail_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=1, stderr=b'boom')

    with patch.object(mu, '_ffmpeg_exe', return_value='ffmpeg'), \
         patch.object(mu.subprocess, 'run', side_effect=fail_run):
        assert mu.uniquify_video(src, '') is None


def test_uniquify_video_no_ffmpeg_returns_none(tmp_path):
    src = str(tmp_path / 'clip.mp4')
    with open(src, 'wb') as f:
        f.write(b'rawvideo')
    with patch.object(mu, '_ffmpeg_exe', return_value=None):
        assert mu.uniquify_video(src, '') is None
