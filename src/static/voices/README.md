# Голосовые модели TTS (piper)

Здесь лежат офлайн-модели голоса **piper** для narrated-Reel пивота (Фаза 1).
Модуль [`src/producers/tts.py`](../../producers/tts.py) ищет голос как
`<TTS_VOICES_DIR>/<TTS_VOICE>.onnx` (+ соседний `.onnx.json`). Дефолт:
`pt_BR-faber-medium`.

Каждый голос = **два файла**:

- `<voice>.onnx` — веса модели (~20–60 МБ для `medium`);
- `<voice>.onnx.json` — конфиг (частота, фонемы, спикер).

## Как положить голос

Вариант A — утилита piper (нужен установленный `piper-tts`, ставится в Фазе 1):

```bash
python -m piper.download_voices pt_BR-faber-medium --data-dir src/static/voices
```

Вариант B — прямая загрузка из rhasspy/piper-voices (HuggingFace), например PT-BR:

```
src/static/voices/pt_BR-faber-medium.onnx
src/static/voices/pt_BR-faber-medium.onnx.json
```

Для футбольного (PT-PT) канала попробовать `pt_PT-tugão-medium` и сравнить качество.

## Коммитить бинарь или качать в CI?

По умолчанию `*.onnx` / `*.onnx.json` **в `.gitignore`** — чтобы 60-МБ бинарь не
попал в git случайно. Два пути к рантайму на раннере (решаем в Фазе 1):

1. **Вендоринг**: убрать эти маски из `.gitignore` и закоммитить модель (репо +~30–60 МБ,
   зато полностью офлайн, без сетевого шага).
2. **Загрузка в CI**: качать в шаге workflow (`actions/cache` + download). Возвращает
   сетевой шаг, но git остаётся лёгким.

Пока модели нет — `tts.synthesize()` возвращает `None` (fail-open), и бот работает
как раньше.
