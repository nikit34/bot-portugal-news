import pytest

import src.producers.digest_video as dv


@pytest.fixture
def items(tmp_path):
    made = []
    for i in range(6):
        path = tmp_path / f'pic{i}.jpg'
        path.write_bytes(b'jpeg')
        made.append({'path': str(path), 'text': f'Notícia número {i} sobre o campeonato.'})
    return made


def _stub_pipeline(monkeypatch, seconds=30.0, segment_ok=True):
    """Заглушки на весь тяжёлый низ: ffmpeg/piper/Pillow в юнит-тестах не гоняем."""
    monkeypatch.setattr(dv, '_ffmpeg_exe', lambda: '/usr/bin/ffmpeg')
    monkeypatch.setattr(dv.tts, 'is_available', lambda: True)
    monkeypatch.setattr(dv.tts, 'synthesize', lambda text, max_chars=None: '/tmp/v.wav')
    monkeypatch.setattr(dv.tts, 'audio_duration', lambda path: seconds)
    monkeypatch.setattr(dv, 'render_headline_story',
                        lambda src, head, brand=None, size=None: src + '.frame.jpg')
    monkeypatch.setattr(dv, 'discard_overlay', lambda p: None)
    monkeypatch.setattr(dv, '_safe_remove', lambda p: None)
    rendered = []

    def fake_render(frame, voice, out, motion=None, size=None, max_seconds=None, timeout=None):
        if not segment_ok:
            return None
        rendered.append({'out': out, 'size': size, 'max_seconds': max_seconds})
        return out

    monkeypatch.setattr(dv, 'render_reel', fake_render)
    monkeypatch.setattr(dv, '_concat', lambda segs, out: True)
    return rendered


def test_builds_digest_from_enough_items(monkeypatch, items):
    rendered = _stub_pipeline(monkeypatch)
    monkeypatch.setattr(dv, 'DIGEST_MIN_ITEMS', 4)
    monkeypatch.setattr(dv, 'DIGEST_ITEMS', 8)

    path, headlines = dv.build_digest_video(items, out_mp4='/tmp/digest.mp4')

    assert path == '/tmp/digest.mp4'
    assert len(headlines) == 6
    # Формат ФИДА (4:5), а не Reels: вертикаль 9:16 Meta утащила бы в Reels, где
    # ставка за просмотр в десятки раз ниже.
    assert all(seg['size'] == (dv.DIGEST_W, dv.DIGEST_H) for seg in rendered)


def test_skips_when_too_few_items(monkeypatch, items):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(dv, 'DIGEST_MIN_ITEMS', 4)

    path, headlines = dv.build_digest_video(items[:3])

    assert path is None and headlines == []


def test_skips_when_total_too_short(monkeypatch, items):
    # 6 сюжетов по 5с = 30с: слишком коротко для «длинного видео», рекламных
    # вставок не будет — публиковать такое смысла нет.
    _stub_pipeline(monkeypatch, seconds=5.0)
    monkeypatch.setattr(dv, 'DIGEST_MIN_ITEMS', 4)
    monkeypatch.setattr(dv, 'DIGEST_MIN_SECONDS', 90)

    path, _ = dv.build_digest_video(items)

    assert path is None


def test_stops_adding_items_at_length_cap(monkeypatch, items):
    rendered = _stub_pipeline(monkeypatch, seconds=60.0)
    monkeypatch.setattr(dv, 'DIGEST_MIN_ITEMS', 2)
    monkeypatch.setattr(dv, 'DIGEST_MAX_SECONDS', 150)

    path, headlines = dv.build_digest_video(items, out_mp4='/tmp/d.mp4')

    # 60 + 60 + 30 (обрезан остатком бюджета) = 150с, дальше не добираем
    assert path == '/tmp/d.mp4'
    assert len(headlines) == 3
    assert rendered[-1]['max_seconds'] == 30


def test_fail_open_without_ffmpeg(monkeypatch, items):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(dv, '_ffmpeg_exe', lambda: None)
    assert dv.build_digest_video(items) == (None, [])


def test_fail_open_without_tts(monkeypatch, items):
    # Без своей озвучки ролик перестаёт быть оригинальным по построению — именно
    # то, за что Meta снимает монетизацию. Лучше не публиковать ничего.
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(dv.tts, 'is_available', lambda: False)
    assert dv.build_digest_video(items) == (None, [])


def test_ignores_items_with_missing_media(monkeypatch, items, tmp_path):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(dv, 'DIGEST_MIN_ITEMS', 4)
    broken = items + [{'path': str(tmp_path / 'gone.jpg'), 'text': 'x'}, {'path': None, 'text': 'y'}]

    path, headlines = dv.build_digest_video(broken, out_mp4='/tmp/d.mp4')

    assert path == '/tmp/d.mp4' and len(headlines) == 6


def test_concat_list_escapes_quotes(monkeypatch, tmp_path):
    # ffmpeg concat-демуксер разбирает 'file ...' по кавычкам: путь с апострофом
    # (частый случай в португальских именах) сломал бы список.
    monkeypatch.setattr(dv, 'tmp_folder', str(tmp_path))
    monkeypatch.setattr(dv, '_ffmpeg_exe', lambda: '/usr/bin/ffmpeg')
    written = {}

    class _Result:
        returncode = 0
        stderr = b''

    def fake_run(cmd, **kwargs):
        list_path = cmd[cmd.index('-i') + 1]
        written['content'] = open(list_path).read()
        open(cmd[-1], 'w').close()
        return _Result()

    monkeypatch.setattr(dv.subprocess, 'run', fake_run)
    seg = tmp_path / "o'brien.mp4"
    seg.write_bytes(b'x')

    assert dv._concat([str(seg)], str(tmp_path / 'out.mp4')) is True
    assert r"'\''" in written['content']


def test_caption_lists_every_headline():
    caption = dv.build_digest_caption('Resumo do dia — 24.07.2026', ['A vitória', 'O treinador'])
    assert caption.startswith('Resumo do dia — 24.07.2026')
    assert '1. A vitória' in caption and '2. O treinador' in caption


def test_segment_failure_does_not_abort_digest(monkeypatch, items):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(dv, 'DIGEST_MIN_ITEMS', 4)
    calls = {'n': 0}
    real_render = dv.render_reel

    def flaky(frame, voice, out, **kwargs):
        calls['n'] += 1
        return None if calls['n'] == 2 else real_render(frame, voice, out, **kwargs)

    monkeypatch.setattr(dv, 'render_reel', flaky)

    path, headlines = dv.build_digest_video(items, out_mp4='/tmp/d.mp4')

    assert path == '/tmp/d.mp4'
    assert len(headlines) == 5          # один сегмент выпал, ролик собрался из остальных
