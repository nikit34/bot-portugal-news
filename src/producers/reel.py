import os
import logging
import subprocess

from src.producers.media_uniquify import _ffmpeg_exe
from src.producers import tts
from src.producers.story_overlay import render_headline_story, extract_headline, discard_overlay
from src.static.settings import (
    REEL_RENDER_ENABLED,
    REEL_MOTION_ENABLED,
    REEL_MAX_SECONDS,
    REEL_RENDER_TIMEOUT_SECONDS,
)

logger = logging.getLogger('app')

REEL_W, REEL_H, REEL_FPS = 1080, 1920, 30


def _video_filter(duration, motion):
    # Плашка story_overlay уже 1080×1920. Без движения — только гарантия размера/SAR
    # + yuv420p. С движением — лёгкий Ken Burns: апскейлим в 1.5× ради запаса под зум,
    # затем zoompan сводит обратно к 1080×1920 (медленный зум-ин).
    if not motion:
        return (f"scale={REEL_W}:{REEL_H}:force_original_aspect_ratio=increase,"
                f"crop={REEL_W}:{REEL_H},setsar=1,format=yuv420p")
    frames = max(1, int((duration + 0.5) * REEL_FPS))   # d в кадрах; +0.5с запас под -shortest
    return (f"scale={REEL_W * 3 // 2}:{REEL_H * 3 // 2},"
            f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:"
            f"s={REEL_W}x{REEL_H}:fps={REEL_FPS},setsar=1,format=yuv420p")


def render_reel(frame_path, voice_path, out_mp4, motion=None):
    """Собрать вертикальный Reel из статичной плашки + WAV-озвучки через ffmpeg.
    Длина = длина аудио (капнута REEL_MAX_SECONDS). Путь к .mp4 или None (fail-open)."""
    exe = _ffmpeg_exe()
    if not exe:
        logger.warning("[reel] no ffmpeg available; skipping reel render")
        return None
    if not frame_path or not os.path.isfile(frame_path):
        return None
    duration = tts.audio_duration(voice_path)
    if not duration or duration <= 0:
        logger.warning("[reel] cannot determine voice duration; skipping")
        return None
    duration = min(duration, REEL_MAX_SECONDS)
    if motion is None:
        motion = REEL_MOTION_ENABLED

    vf = _video_filter(duration, motion)
    cmd = [
        exe, '-y', '-loglevel', 'error',
        '-loop', '1', '-i', frame_path, '-i', voice_path,
        '-filter_complex', f"[0:v]{vf}[v]",
        '-map', '[v]', '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
        '-r', str(REEL_FPS), '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k', '-af', 'loudnorm',
        '-t', f"{duration:.3f}", '-movflags', '+faststart', '-shortest', out_mp4,
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=REEL_RENDER_TIMEOUT_SECONDS)
        if result.returncode != 0 or not os.path.exists(out_mp4):
            logger.warning(
                f"[reel] ffmpeg failed (rc={result.returncode}): "
                f"{result.stderr.decode('utf-8', 'replace')[:300]}")
            _safe_remove(out_mp4)
            return None
        return out_mp4
    except Exception as e:
        logger.warning(f"[reel] render failed: {e}")
        _safe_remove(out_mp4)
        return None


def build_reel(src_path, message):
    """Из новости (картинка + текст) собрать narrated-Reel: плашка 9:16 с заголовком
    + наша TTS-озвучка + Ken Burns. None => публикуем как раньше (fail-open).

    Порядок дешевле→дороже: флаг → файл → доступность TTS → заголовок → рендер плашки
    → синтез голоса → сборка видео. Временные плашка/озвучка убираются в finally.
    """
    if not REEL_RENDER_ENABLED:
        return None
    if not src_path or not os.path.isfile(src_path):
        return None
    if not tts.is_available():          # нет piper/модели — даже не начинаем рендер
        return None
    headline = extract_headline(message)
    if not headline:
        return None

    frame = None
    voice = None
    try:
        frame = render_headline_story(src_path, headline)   # 1080×1920 плашка с заголовком
        if not frame:
            return None
        voice = tts.synthesize(message)                     # озвучка текста новости
        if not voice:
            return None
        out_mp4 = os.path.splitext(src_path)[0] + '.reel.mp4'
        return render_reel(frame, voice, out_mp4)
    except Exception as e:
        logger.warning(f"[reel] build failed for {src_path}: {e}")
        return None
    finally:
        discard_overlay(frame)          # плашка уже впечатана в видео
        _safe_remove(voice)             # временный wav


def _safe_remove(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
