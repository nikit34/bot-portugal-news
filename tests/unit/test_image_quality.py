from PIL import Image

import src.processor.image_filter as imgf
from src.parsers.rss.channels.pt.rtp import _upscale


def _make_image(path, width, height):
    Image.new('RGB', (width, height), color='blue').save(path)
    return str(path)


def test_tiny_thumbnail_is_low_quality(tmp_path, monkeypatch):
    monkeypatch.setattr(imgf, 'IMAGE_MIN_WIDTH', 500)
    monkeypatch.setattr(imgf, 'IMAGE_MIN_HEIGHT', 300)
    # UOL 142x100 and record 220x220 — both rejected
    assert imgf.is_low_quality_image(_make_image(tmp_path / 'uol.png', 142, 100)) is True
    assert imgf.is_low_quality_image(_make_image(tmp_path / 'rec.png', 220, 220)) is True
    # rtp 350x197 — rejected on width
    assert imgf.is_low_quality_image(_make_image(tmp_path / 'rtp.png', 350, 197)) is True


def test_full_size_image_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(imgf, 'IMAGE_MIN_WIDTH', 500)
    monkeypatch.setattr(imgf, 'IMAGE_MIN_HEIGHT', 300)
    # bbc 960x540, gazeta 1064x709, og-standard 1200x630, og-min 600x315 — all kept
    for w, h in [(960, 540), (1064, 709), (1200, 630), (600, 315)]:
        path = _make_image(tmp_path / f'ok_{w}x{h}.png', w, h)
        assert imgf.is_low_quality_image(path) is False


def test_unreadable_path_fails_open(tmp_path):
    assert imgf.is_low_quality_image(str(tmp_path / 'does_not_exist.png')) is False


def test_rtp_upscale_bumps_resizer_params():
    url = ('https://cdn-images.rtp.pt/icm/noticias/images/38/abc'
           '?w=350&q=50&rect=0,0,1499,822&auto=format')
    out = _upscale(url)
    assert 'w=1200' in out and 'w=350' not in out
    assert 'q=80' in out and 'q=50' not in out
    assert 'rect=0,0,1499,822' in out and 'auto=format' in out  # other params untouched


def test_rtp_upscale_leaves_urls_without_params():
    url = 'https://cdn-images.rtp.pt/icm/images/ef/abc_N.jpg'
    assert _upscale(url) == url
