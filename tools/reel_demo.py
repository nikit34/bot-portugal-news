#!/usr/bin/env python3
"""Реальный end-to-end прогон narrated-Reel: текст -> piper TTS -> плашка 9:16 ->
ffmpeg -> вертикальный mp4. Пишет tmp/demo_reel.mp4 и валидирует его (h264+aac,
длина > 0). Запускается на linux, где стоит piper (см. reel-smoke.yml); локально на
macOS piper недоступен (нет wheel piper-phonemize) — скрипт честно завершится с
кодом 2.

    python tools/fetch_piper_voice.py && python tools/reel_demo.py
"""
import os
import sys
import shutil
import subprocess

sys.path.insert(0, os.getcwd())

from PIL import Image                                     # noqa: E402
from src.producers import tts, reel                       # noqa: E402
from src.producers.media_uniquify import _ffmpeg_exe      # noqa: E402

TEXT = ("Benfica venceu o clássico por dois a um em plena Luz. "
        "Veja os melhores momentos e a reação do treinador após a partida.")


def main():
    # Форсируем фичу для демо независимо от env-дефолтов (в проде это флаги).
    tts.TTS_ENABLED = True
    reel.REEL_RENDER_ENABLED = True

    if not tts.is_available():
        print(f"[reel-demo] piper/voice NOT available (voice={tts._resolve_voice_path()}); "
              f"run tools/fetch_piper_voice.py on a linux host with piper-tts installed")
        sys.exit(2)

    os.makedirs("tmp", exist_ok=True)
    src = os.path.join("tmp", "demo_src.jpg")
    Image.new("RGB", (1080, 1920), (15, 20, 35)).save(src, "JPEG", quality=90)

    out = reel.build_reel(src, TEXT)
    if not out or not os.path.isfile(out):
        print("[reel-demo] FAILED: build_reel returned nothing")
        sys.exit(1)

    info = subprocess.run([_ffmpeg_exe(), "-i", out], stderr=subprocess.PIPE).stderr.decode("utf-8", "replace")
    has_v = "Video: h264" in info
    has_a = "Audio: aac" in info
    dur = next((l.strip() for l in info.splitlines() if "Duration" in l), "no duration")
    print(f"[reel-demo] out={out} size={os.path.getsize(out)}B video={has_v} audio={has_a} | {dur}")
    if not (has_v and has_a):
        print("[reel-demo] FAILED: output is not a valid video+audio mp4")
        print(info[:600])
        sys.exit(1)

    shutil.copy(out, os.path.join("tmp", "demo_reel.mp4"))
    print("[reel-demo] OK — real narrated reel rendered end-to-end")


if __name__ == "__main__":
    main()
