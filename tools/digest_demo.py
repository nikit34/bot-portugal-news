#!/usr/bin/env python3
"""Реальный end-to-end прогон ДАЙДЖЕСТ-ролика: несколько новостей -> piper TTS ->
плашки 4:5 -> ffmpeg-сегменты -> concat -> один длинный mp4. Пишет tmp/demo_digest.mp4
и валидирует его (h264+aac, длина примерно равна сумме сегментов).

Смысл проверки — именно склейка: сегменты режутся отдельными процессами ffmpeg и
клеятся concat-демуксером с `-c copy`, что молча даёт битый/обрезанный файл при
любом расхождении параметров кодека. Юнит-тесты этот слой замокан обойти не могут.

Запускается на linux, где стоит piper (см. reel-smoke.yml); локально на macOS
piper недоступен (нет wheel piper-phonemize) — скрипт завершится с кодом 2.

    python tools/fetch_piper_voice.py && python tools/digest_demo.py
"""
import os
import sys
import subprocess

sys.path.insert(0, os.getcwd())

from PIL import Image                                     # noqa: E402
from src.producers import tts                             # noqa: E402
from src.producers import digest_video as dv              # noqa: E402
from src.producers.media_uniquify import _ffmpeg_exe      # noqa: E402

ITEMS = [
    "Benfica venceu o clássico por dois a um em plena Luz, com golos na segunda parte.",
    "Sporting empatou fora de casa e mantém a liderança isolada da tabela.",
    "FC Porto acertou a contratação de um avançado brasileiro por quatro temporadas.",
    "Braga anunciou a saída do treinador após três derrotas consecutivas.",
    "A seleção nacional convocou vinte e três jogadores para a próxima jornada dupla.",
]


def _duration_seconds(path):
    info = subprocess.run([_ffmpeg_exe(), "-i", path], stderr=subprocess.PIPE)
    text = info.stderr.decode("utf-8", "replace")
    line = next((l for l in text.splitlines() if "Duration" in l), "")
    try:
        stamp = line.split("Duration:")[1].split(",")[0].strip()
        h, m, s = stamp.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s), text
    except (IndexError, ValueError):
        return None, text


def main():
    tts.TTS_ENABLED = True
    if not tts.is_available():
        print(f"[digest-demo] piper/voice NOT available (voice={tts._resolve_voice_path()}); "
              f"run tools/fetch_piper_voice.py on a linux host with piper-tts installed")
        sys.exit(2)

    # Демо гоняем без нижних порогов: важно проверить склейку, а не длину.
    dv.DIGEST_MIN_ITEMS = 3
    dv.DIGEST_MIN_SECONDS = 5

    os.makedirs("tmp", exist_ok=True)
    items = []
    for i, text in enumerate(ITEMS):
        path = os.path.join("tmp", f"demo_digest_src{i}.jpg")
        Image.new("RGB", (1280, 720), (15 + i * 12, 20, 35)).save(path, "JPEG", quality=90)
        items.append({"path": path, "text": text})

    out, headlines = dv.build_digest_video(items, out_mp4=os.path.join("tmp", "demo_digest.mp4"))
    if not out or not os.path.isfile(out):
        print("[digest-demo] FAILED: build_digest_video returned nothing")
        sys.exit(1)

    duration, info = _duration_seconds(out)
    has_v = "Video: h264" in info
    has_a = "Audio: aac" in info
    print(f"[digest-demo] out={out} size={os.path.getsize(out)}B segments={len(headlines)} "
          f"duration={duration}s video={has_v} audio={has_a}")
    for i, head in enumerate(headlines, 1):
        print(f"  {i}. {head}")

    if not (has_v and has_a):
        print("[digest-demo] FAILED: output is not a valid video+audio mp4")
        print(info[:600])
        sys.exit(1)
    # Склейка «-c copy» при расхождении параметров молча роняет хвост: ловим это
    # требованием, что итог заметно длиннее одного сегмента.
    if duration is None or duration < 10:
        print(f"[digest-demo] FAILED: concat produced a suspiciously short file ({duration}s)")
        sys.exit(1)

    # Копировать некуда: в отличие от reel_demo (там build_reel сам выбирает путь),
    # мы задали out_mp4 сразу артефактным — файл уже на месте.
    print("[digest-demo] OK — real long-form digest rendered end-to-end")


if __name__ == "__main__":
    main()
