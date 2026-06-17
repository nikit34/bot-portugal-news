import os

import pytest
from PIL import Image

import src.producers.story_overlay as so


def _make_image(path, size=(1280, 720), color=(40, 120, 60)):
    Image.new('RGB', size, color).save(path)
    return str(path)


# --- extract_headline ----------------------------------------------------

def test_headline_takes_first_sentence():
    text = "Benfica vence o Porto por 2-1. Restante texto do artigo segue aqui."
    assert so.extract_headline(text, 200) == "Benfica vence o Porto por 2-1."


def test_headline_first_line_when_multiline():
    text = "Sporting goleia em Alvalade\n\nO jogo terminou com mais detalhes."
    assert so.extract_headline(text, 200) == "Sporting goleia em Alvalade"


def test_headline_truncates_on_word_boundary_with_ellipsis():
    text = "Benfica conquista mais uma vitoria importante na corrida pelo titulo nacional desta epoca"
    out = so.extract_headline(text, 40)
    assert out.endswith('…')
    assert len(out) <= 41          # 40 chars + ellipsis
    assert not out[:-1].endswith(' ')  # trimmed at a word boundary, no trailing space


def test_headline_keeps_early_abbreviation_dot():
    # A '.' within the first 20 chars must NOT cut the headline (e.g. "S.L.").
    text = "S.L. Benfica vence o classico da jornada"
    assert so.extract_headline(text, 200) == text


def test_headline_empty_input():
    assert so.extract_headline('', 90) == ''
    assert so.extract_headline('   \n  ', 90) == ''


# --- render_headline_story ------------------------------------------------

def test_render_produces_9x16_jpeg(tmp_path):
    src = _make_image(tmp_path / 'src.png')
    out = so.render_headline_story(src, "Benfica vence o Porto no classico")
    assert out and os.path.isfile(out)
    assert out.endswith('.story.jpg')
    with Image.open(out) as img:
        assert img.size == (so.STORY_W, so.STORY_H)
        assert img.format == 'JPEG'


def test_render_returns_none_on_unreadable_image(tmp_path):
    bad = tmp_path / 'bad.jpg'
    bad.write_bytes(b'not-an-image')
    assert so.render_headline_story(str(bad), "headline") is None


def test_render_handles_tall_source(tmp_path):
    # Portrait source must still yield a full 9:16 canvas (contained, not crashing).
    src = _make_image(tmp_path / 'tall.png', size=(600, 1600))
    out = so.render_headline_story(src, "Manchete vertical de teste para o story")
    with Image.open(out) as img:
        assert img.size == (so.STORY_W, so.STORY_H)


# --- build_story_image ----------------------------------------------------

def test_build_disabled_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(so, 'STORY_TEXT_OVERLAY_ENABLED', False)
    src = _make_image(tmp_path / 'src.png')
    assert so.build_story_image(src, "headline") is None


def test_build_none_when_no_file(monkeypatch):
    monkeypatch.setattr(so, 'STORY_TEXT_OVERLAY_ENABLED', True)
    assert so.build_story_image(None, "headline") is None
    assert so.build_story_image('/nope/missing.jpg', "headline") is None


def test_build_none_when_no_headline(tmp_path, monkeypatch):
    monkeypatch.setattr(so, 'STORY_TEXT_OVERLAY_ENABLED', True)
    src = _make_image(tmp_path / 'src.png')
    assert so.build_story_image(src, '') is None


def test_build_renders_for_real_image(tmp_path, monkeypatch):
    monkeypatch.setattr(so, 'STORY_TEXT_OVERLAY_ENABLED', True)
    src = _make_image(tmp_path / 'src.png')
    out = so.build_story_image(src, "Benfica vence o Porto no classico")
    assert out and os.path.isfile(out)
    with Image.open(out) as img:
        assert img.size == (so.STORY_W, so.STORY_H)


def test_build_with_brand_kicker(tmp_path, monkeypatch):
    monkeypatch.setattr(so, 'STORY_TEXT_OVERLAY_ENABLED', True)
    src = _make_image(tmp_path / 'src.png')
    # brand is read by render via the module-level default; pass through explicitly
    out = so.render_headline_story(src, "Manchete com marca", brand='Noticias Portugal')
    with Image.open(out) as img:
        assert img.size == (so.STORY_W, so.STORY_H)


# --- discard_overlay ------------------------------------------------------

def test_discard_removes_file(tmp_path):
    p = tmp_path / 'x.story.jpg'
    p.write_bytes(b'data')
    so.discard_overlay(str(p))
    assert not p.exists()


def test_discard_tolerates_missing(tmp_path):
    so.discard_overlay(None)               # no-op
    so.discard_overlay(str(tmp_path / 'absent.jpg'))  # no raise
