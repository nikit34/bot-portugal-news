#!/usr/bin/env python3
"""Скачать голосовую модель piper (.onnx + .onnx.json) в src/static/voices/.

Одной командой добывает голос из официального репозитория rhasspy/piper-voices
(HuggingFace). Нужен для narrated-Reel пивота (Фаза 1). Использует только stdlib
(urllib), чтобы работать и в CI, и локально без доп-зависимостей.

    python tools/fetch_piper_voice.py                    # дефолт: pt_BR-faber-medium
    python tools/fetch_piper_voice.py pt_PT-tugao-medium # другой голос

ВАЖНО: piper САМ (piper-tts) ставится только там, где есть wheel piper-phonemize —
это linux (CI/деплой). На macOS arm64 wheel'а нет, поэтому реальный синтез гоняем
на linux (см. .github/workflows/reel-smoke.yml).
"""
import os
import sys
import urllib.request

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# voice-name -> относительный путь в репозитории (без расширения)
VOICES = {
    "pt_BR-faber-medium": "pt/pt_BR/faber/medium/pt_BR-faber-medium",
    "pt_BR-edresson-low": "pt/pt_BR/edresson/low/pt_BR-edresson-low",
    "pt_PT-tugao-medium": "pt/pt_PT/tugão/medium/pt_PT-tugão-medium",
}

DEST = os.path.join("src", "static", "voices")


def _download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "bot-portugal-news/voice-fetch"})
    last = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp, open(out_path, "wb") as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
            return
        except Exception as e:               # noqa: BLE001 — retry any transient failure
            last = e
            print(f"  retry {attempt}/3: {e}")
    raise SystemExit(f"download failed after retries: {url} ({last})")


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "pt_BR-faber-medium"
    rel = VOICES.get(name)
    if not rel:
        raise SystemExit(f"unknown voice '{name}'; known: {', '.join(VOICES)}")
    os.makedirs(DEST, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        out_path = os.path.join(DEST, name + ext)
        if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            print(f"exists: {out_path} ({os.path.getsize(out_path)} bytes)")
            continue
        url = f"{BASE}/{rel}{ext}?download=true"
        print(f"downloading {url}")
        _download(url, out_path)
        print(f"saved: {out_path} ({os.path.getsize(out_path)} bytes)")
    print(f"voice '{name}' ready in {DEST}")


if __name__ == "__main__":
    main()
