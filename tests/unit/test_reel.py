import os
import types

import src.producers.reel as reel


# --- video filter ------------------------------------------------------------

def test_video_filter_motion_has_zoompan():
    vf = reel._video_filter(5.0, motion=True)
    assert 'zoompan' in vf and 'format=yuv420p' in vf and 'fps=30' in vf


def test_video_filter_motion_is_centered():
    # Regression guard: zoompan defaults x/y to 0,0 (top-left), which crops the
    # bottom-anchored headline off-frame. The zoom MUST be centered.
    vf = reel._video_filter(5.0, motion=True)
    assert "x='iw/2-(iw/zoom/2)'" in vf and "y='ih/2-(ih/zoom/2)'" in vf


def test_video_filter_static_has_no_zoompan():
    vf = reel._video_filter(5.0, motion=False)
    assert 'zoompan' not in vf
    assert 'crop=1080:1920' in vf and 'format=yuv420p' in vf


# --- render_reel (ffmpeg mocked) ---------------------------------------------

def _fake_run_success(cmd, **kwargs):
    with open(cmd[-1], 'wb') as f:            # last arg = output path
        f.write(b'\x00\x00fakemp4data')
    return types.SimpleNamespace(returncode=0, stderr=b'')


def test_render_reel_no_ffmpeg_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, '_ffmpeg_exe', lambda: None)
    frame = tmp_path / 'f.jpg'
    frame.write_bytes(b'x')
    assert reel.render_reel(str(frame), str(tmp_path / 'v.wav'), str(tmp_path / 'o.mp4')) is None


def test_render_reel_missing_frame_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, '_ffmpeg_exe', lambda: 'ffmpeg')
    assert reel.render_reel('/nope/frame.jpg', str(tmp_path / 'v.wav'), str(tmp_path / 'o.mp4')) is None


def test_render_reel_no_duration_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, '_ffmpeg_exe', lambda: 'ffmpeg')
    monkeypatch.setattr(reel.tts, 'audio_duration', lambda p: None)
    frame = tmp_path / 'f.jpg'
    frame.write_bytes(b'x')
    assert reel.render_reel(str(frame), str(tmp_path / 'v.wav'), str(tmp_path / 'o.mp4')) is None


def test_render_reel_ffmpeg_failure_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, '_ffmpeg_exe', lambda: 'ffmpeg')
    monkeypatch.setattr(reel.tts, 'audio_duration', lambda p: 5.0)
    frame = tmp_path / 'f.jpg'
    frame.write_bytes(b'x')

    def fail_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=1, stderr=b'boom')

    monkeypatch.setattr(reel.subprocess, 'run', fail_run)
    out = str(tmp_path / 'o.mp4')
    assert reel.render_reel(str(frame), str(tmp_path / 'v.wav'), out) is None
    assert not os.path.exists(out)


def test_render_reel_success_and_clamps_duration(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, '_ffmpeg_exe', lambda: 'ffmpeg')
    monkeypatch.setattr(reel.tts, 'audio_duration', lambda p: 100.0)   # over the cap
    monkeypatch.setattr(reel, 'REEL_MAX_SECONDS', 12.0)
    frame = tmp_path / 'f.jpg'
    frame.write_bytes(b'x')
    voice = tmp_path / 'v.wav'
    voice.write_bytes(b'x')

    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        return _fake_run_success(cmd, **kwargs)

    monkeypatch.setattr(reel.subprocess, 'run', fake_run)
    out = str(tmp_path / 'o.mp4')
    result = reel.render_reel(str(frame), str(voice), out, motion=False)

    assert result == out and os.path.isfile(out)
    cmd = captured['cmd']
    assert cmd[cmd.index('-t') + 1] == '12.000'          # duration clamped to REEL_MAX_SECONDS
    assert cmd[-1] == out and '-shortest' in cmd


# --- build_reel (orchestration; seams mocked) --------------------------------

def test_build_reel_disabled_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, 'REEL_RENDER_ENABLED', False)
    src = tmp_path / 'src.jpg'
    src.write_bytes(b'x')
    assert reel.build_reel(str(src), 'Benfica vence o Porto.') is None


def test_build_reel_tts_unavailable_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, 'REEL_RENDER_ENABLED', True)
    monkeypatch.setattr(reel.tts, 'is_available', lambda voice_path=None: False)
    src = tmp_path / 'src.jpg'
    src.write_bytes(b'x')
    assert reel.build_reel(str(src), 'Benfica vence o Porto.') is None


def test_build_reel_no_headline_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(reel, 'REEL_RENDER_ENABLED', True)
    monkeypatch.setattr(reel.tts, 'is_available', lambda voice_path=None: True)
    src = tmp_path / 'src.jpg'
    src.write_bytes(b'x')
    assert reel.build_reel(str(src), '') is None            # empty message -> no headline


def test_build_reel_happy_path_cleans_temps(monkeypatch, tmp_path):
    src = tmp_path / 'src.jpg'
    src.write_bytes(b'x')
    frame = tmp_path / 'src.story.jpg'
    frame.write_bytes(b'frame')
    voice = tmp_path / 'v.wav'
    voice.write_bytes(b'wav')

    monkeypatch.setattr(reel, 'REEL_RENDER_ENABLED', True)
    monkeypatch.setattr(reel.tts, 'is_available', lambda voice_path=None: True)
    monkeypatch.setattr(reel, 'render_headline_story', lambda s, h: str(frame))
    monkeypatch.setattr(reel.tts, 'synthesize', lambda m: str(voice))
    monkeypatch.setattr(reel, 'render_reel', lambda f, v, o: o)   # pretend ffmpeg made the mp4

    result = reel.build_reel(str(src), 'Benfica vence o Porto por 2 a 1 na final.')

    assert result == os.path.splitext(str(src))[0] + '.reel.mp4'
    assert not os.path.exists(frame)          # overlay frame discarded
    assert not os.path.exists(voice)          # temp voice removed


def test_build_reel_frame_render_fails_returns_none(monkeypatch, tmp_path):
    src = tmp_path / 'src.jpg'
    src.write_bytes(b'x')
    monkeypatch.setattr(reel, 'REEL_RENDER_ENABLED', True)
    monkeypatch.setattr(reel.tts, 'is_available', lambda voice_path=None: True)
    monkeypatch.setattr(reel, 'render_headline_story', lambda s, h: None)
    assert reel.build_reel(str(src), 'Benfica vence o Porto por 2 a 1.') is None


def test_build_reel_tts_fails_cleans_frame(monkeypatch, tmp_path):
    src = tmp_path / 'src.jpg'
    src.write_bytes(b'x')
    frame = tmp_path / 'src.story.jpg'
    frame.write_bytes(b'frame')

    monkeypatch.setattr(reel, 'REEL_RENDER_ENABLED', True)
    monkeypatch.setattr(reel.tts, 'is_available', lambda voice_path=None: True)
    monkeypatch.setattr(reel, 'render_headline_story', lambda s, h: str(frame))
    monkeypatch.setattr(reel.tts, 'synthesize', lambda m: None)

    assert reel.build_reel(str(src), 'Benfica vence o Porto por 2 a 1.') is None
    assert not os.path.exists(frame)          # frame cleaned up even though synth failed
