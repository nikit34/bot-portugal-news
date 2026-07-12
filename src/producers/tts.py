import os
import re
import time
import wave
import logging

from src.static.sources import tmp_folder
from src.static.settings import (
    TTS_ENABLED,
    TTS_ENGINE,
    TTS_VOICE,
    TTS_VOICES_DIR,
    TTS_VOICE_PATH,
    TTS_MAX_CHARS,
)

logger = logging.getLogger('app')

# Загруженный голос piper переиспользуем между постами одного прогона (load ~сотни мс,
# модель десятки МБ). Ключ — путь к .onnx.
_voice_cache = {}


# --- разрешение модели голоса -----------------------------------------------

def _resolve_voice_path(voice_path=None):
    # Приоритет: явный аргумент > TTS_VOICE_PATH > <TTS_VOICES_DIR>/<TTS_VOICE>.onnx.
    # Возвращаем путь к .onnx, только если рядом есть и сам .onnx, и его .onnx.json
    # (piper грузит конфиг как model_path + '.json'); иначе None (fail-open).
    candidate = voice_path or TTS_VOICE_PATH or os.path.join(TTS_VOICES_DIR, TTS_VOICE + '.onnx')
    if candidate and os.path.isfile(candidate) and os.path.isfile(candidate + '.json'):
        return candidate
    return None


def is_available(voice_path=None):
    """piper импортируется И модель голоса на месте => можно синтезировать.

    Дешёвая предпроверка для вызывающего (reel.py в Фазе 1), чтобы не готовить
    кадр под Reel, если озвучить всё равно нечем.
    """
    if not TTS_ENABLED or TTS_ENGINE != 'piper':
        return False
    if _resolve_voice_path(voice_path) is None:
        return False
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


# --- подготовка текста -------------------------------------------------------

def _clean_text(text):
    # Текст под озвучку: выкидываем URL, хэштеги/меншены и схлопываем пробелы, затем
    # режем до TTS_MAX_CHARS по границе предложения (иначе слова), чтобы Reel был
    # коротким. Возвращаем '' если озвучивать нечего.
    if not text:
        return ''
    t = re.sub(r'https?://\S+', '', text)
    t = re.sub(r'[#@]\w+', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= TTS_MAX_CHARS:
        return t
    clipped = t[:TTS_MAX_CHARS]
    cut = max(clipped.rfind('. '), clipped.rfind('! '), clipped.rfind('? '))
    if cut < TTS_MAX_CHARS // 2:            # граница предложения слишком рано — по слову
        cut = clipped.rfind(' ')
    return (clipped[:cut + 1] if cut > 0 else clipped).strip()


# --- синтез (piper) ----------------------------------------------------------

def _load_voice(voice_path):
    cached = _voice_cache.get(voice_path)
    if cached is not None:
        return cached
    from piper import PiperVoice
    voice = PiperVoice.load(voice_path)     # конфиг <voice_path>.json найдётся рядом
    _voice_cache[voice_path] = voice
    return voice


def _synthesize_to_wav(voice, text, wav_file):
    # API piper дрейфовал между версиями: предпочитаем synthesize_wav(text, wav),
    # иначе synthesize(text, wav). Обе пишут корректный WAV в открытый wave-файл.
    if hasattr(voice, 'synthesize_wav'):
        voice.synthesize_wav(text, wav_file)
    else:
        voice.synthesize(text, wav_file)


def synthesize(text, out_wav=None, voice_path=None):
    """Озвучить text в WAV через piper. Возвращает путь к .wav или None (fail-open).

    Ничего не бросает: выключено / нет piper / нет модели / пустой текст / сбой
    синтеза => None, и вызывающий публикует без озвучки.
    """
    if not TTS_ENABLED or TTS_ENGINE != 'piper':
        return None
    clean = _clean_text(text)
    if not clean:
        return None
    resolved = _resolve_voice_path(voice_path)
    if resolved is None:
        logger.warning(f"[tts] voice model not found (voice={TTS_VOICE}, dir={TTS_VOICES_DIR}); skipping")
        return None
    if out_wav is None:
        out_wav = os.path.join(tmp_folder, str(time.time_ns()) + '.tts.wav')
    try:
        voice = _load_voice(resolved)
        with wave.open(out_wav, 'wb') as wav_file:
            _synthesize_to_wav(voice, clean, wav_file)
        # >44 байт = что-то сверх пустого WAV-заголовка (44 байта) реально записано.
        if os.path.isfile(out_wav) and os.path.getsize(out_wav) > 44:
            return out_wav
        logger.warning("[tts] piper produced empty wav; skipping")
        _safe_remove(out_wav)
        return None
    except Exception as e:
        logger.warning(f"[tts] synthesis failed (voice={resolved}): {e}")
        _safe_remove(out_wav)
        return None


# --- длительность аудио (для сборки Reel в Фазе 1) ---------------------------

def audio_duration(wav_path):
    """Длительность WAV в секундах через stdlib `wave` (ffprobe в imageio-ffmpeg
    нет). None при ошибке/отсутствии файла."""
    if not wav_path or not os.path.isfile(wav_path):
        return None
    try:
        with wave.open(wav_path, 'rb') as w:
            rate = w.getframerate()
            return (w.getnframes() / float(rate)) if rate else None
    except Exception as e:
        logger.warning(f"[tts] cannot read wav duration for {wav_path}: {e}")
        return None


def _safe_remove(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
