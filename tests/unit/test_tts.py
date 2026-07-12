import os
import sys
import types
import wave

import src.producers.tts as tts


# --- voice-path resolution ---------------------------------------------------

def test_resolve_requires_both_onnx_and_json(monkeypatch, tmp_path):
    onnx = tmp_path / 'v.onnx'
    onnx.write_bytes(b'x')
    monkeypatch.setattr(tts, 'TTS_VOICE_PATH', str(onnx))
    assert tts._resolve_voice_path() is None            # no .onnx.json sibling yet
    (tmp_path / 'v.onnx.json').write_text('{}')
    assert tts._resolve_voice_path() == str(onnx)


def test_resolve_explicit_arg_wins(monkeypatch, tmp_path):
    onnx = tmp_path / 'explicit.onnx'
    onnx.write_bytes(b'x')
    (tmp_path / 'explicit.onnx.json').write_text('{}')
    monkeypatch.setattr(tts, 'TTS_VOICE_PATH', '/does/not/exist.onnx')
    assert tts._resolve_voice_path(str(onnx)) == str(onnx)


# --- text preparation --------------------------------------------------------

def test_clean_text_strips_urls_tags_and_whitespace(monkeypatch):
    monkeypatch.setattr(tts, 'TTS_MAX_CHARS', 600)
    out = tts._clean_text('Benfica venceu!  #Benfica @sport https://t.me/x veja')
    assert 'http' not in out and '#' not in out and '@' not in out
    assert 'Benfica venceu!' in out and '  ' not in out


def test_clean_text_limits_length(monkeypatch):
    monkeypatch.setattr(tts, 'TTS_MAX_CHARS', 20)
    out = tts._clean_text('uma frase. ' + 'x' * 100)
    assert len(out) <= 20 and out == 'uma frase.'


def test_clean_text_empty():
    assert tts._clean_text('') == ''
    assert tts._clean_text(None) == ''


# --- synthesize (piper mocked via seams) -------------------------------------

def _write_valid_wav(wav_file, seconds=0.1, rate=16000):
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(rate)
    wav_file.writeframes(b'\x00\x00' * int(rate * seconds))


def test_synthesize_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(tts, 'TTS_ENABLED', False)
    assert tts.synthesize('x', voice_path='/nope.onnx') is None


def test_synthesize_empty_after_clean_returns_none(monkeypatch):
    monkeypatch.setattr(tts, 'TTS_ENABLED', True)
    assert tts.synthesize('  #tag @a https://x.com  ', voice_path='/nope.onnx') is None


def test_synthesize_no_voice_model_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, 'TTS_ENABLED', True)
    monkeypatch.setattr(tts, 'TTS_VOICE_PATH', '')
    monkeypatch.setattr(tts, 'TTS_VOICES_DIR', str(tmp_path))   # empty dir
    monkeypatch.setattr(tts, 'TTS_VOICE', 'missing')
    assert tts.synthesize('texto qualquer para narrar') is None


def test_synthesize_happy_path_writes_wav(monkeypatch, tmp_path):
    onnx = tmp_path / 'v.onnx'
    onnx.write_bytes(b'x')
    (tmp_path / 'v.onnx.json').write_text('{}')
    monkeypatch.setattr(tts, 'TTS_ENABLED', True)
    monkeypatch.setattr(tts, '_load_voice', lambda p: object())
    monkeypatch.setattr(tts, '_synthesize_to_wav',
                        lambda voice, text, wf: _write_valid_wav(wf, seconds=0.1))

    out = str(tmp_path / 'o.wav')
    result = tts.synthesize('Olá mundo, isto é um teste.', out_wav=out, voice_path=str(onnx))

    assert result == out and os.path.isfile(out)
    assert abs(tts.audio_duration(out) - 0.1) < 0.01


def test_synthesize_fail_open_on_synth_error(monkeypatch, tmp_path):
    onnx = tmp_path / 'v.onnx'
    onnx.write_bytes(b'x')
    (tmp_path / 'v.onnx.json').write_text('{}')
    monkeypatch.setattr(tts, 'TTS_ENABLED', True)

    def boom(_path):
        raise RuntimeError('onnxruntime missing')

    monkeypatch.setattr(tts, '_load_voice', boom)
    out = str(tmp_path / 'o.wav')
    assert tts.synthesize('texto', out_wav=out, voice_path=str(onnx)) is None
    assert not os.path.exists(out)                  # partial output cleaned up


def test_synthesize_empty_wav_is_rejected(monkeypatch, tmp_path):
    onnx = tmp_path / 'v.onnx'
    onnx.write_bytes(b'x')
    (tmp_path / 'v.onnx.json').write_text('{}')
    monkeypatch.setattr(tts, 'TTS_ENABLED', True)
    monkeypatch.setattr(tts, '_load_voice', lambda p: object())
    # writes only the header (0 frames) -> file <= 44 bytes -> rejected
    monkeypatch.setattr(tts, '_synthesize_to_wav',
                        lambda voice, text, wf: _write_valid_wav(wf, seconds=0))

    out = str(tmp_path / 'o.wav')
    assert tts.synthesize('texto', out_wav=out, voice_path=str(onnx)) is None
    assert not os.path.exists(out)


# --- audio_duration ----------------------------------------------------------

def test_audio_duration_real_wav(tmp_path):
    p = str(tmp_path / 'a.wav')
    with wave.open(p, 'wb') as w:
        _write_valid_wav(w, seconds=0.5)
    assert abs(tts.audio_duration(p) - 0.5) < 0.001


def test_audio_duration_missing_file():
    assert tts.audio_duration('/nope/none.wav') is None


def test_audio_duration_bad_file(tmp_path):
    p = tmp_path / 'bad.wav'
    p.write_bytes(b'not a wav at all')
    assert tts.audio_duration(str(p)) is None


# --- is_available ------------------------------------------------------------

def test_is_available_true_with_model_and_piper(monkeypatch, tmp_path):
    onnx = tmp_path / 'v.onnx'
    onnx.write_bytes(b'x')
    (tmp_path / 'v.onnx.json').write_text('{}')
    monkeypatch.setattr(tts, 'TTS_ENABLED', True)
    monkeypatch.setitem(sys.modules, 'piper', types.ModuleType('piper'))
    assert tts.is_available(voice_path=str(onnx)) is True


def test_is_available_false_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, 'TTS_ENABLED', True)
    monkeypatch.setattr(tts, 'TTS_VOICE_PATH', '')
    monkeypatch.setattr(tts, 'TTS_VOICES_DIR', str(tmp_path))
    monkeypatch.setattr(tts, 'TTS_VOICE', 'missing')
    assert tts.is_available() is False


def test_is_available_false_when_disabled(monkeypatch):
    monkeypatch.setattr(tts, 'TTS_ENABLED', False)
    assert tts.is_available(voice_path='/whatever.onnx') is False
