# Голосовые модели TTS (piper)

Здесь лежат офлайн-модели голоса **piper** для narrated-Reel пивота (Фаза 1).
Модуль [`src/producers/tts.py`](../../producers/tts.py) ищет голос как
`<TTS_VOICES_DIR>/<TTS_VOICE>.onnx` (+ соседний `.onnx.json`). Дефолт:
`pt_BR-faber-medium`.

Каждый голос = **два файла**:

- `<voice>.onnx` — веса модели (~20–60 МБ для `medium`);
- `<voice>.onnx.json` — конфиг (частота, фонемы, спикер).

## Как положить голос

**Проще всего** — скрипт в репозитории (только stdlib, качает из rhasspy/piper-voices):

```bash
python tools/fetch_piper_voice.py                     # дефолт pt_BR-faber-medium
python tools/fetch_piper_voice.py pt_PT-tugao-medium  # PT-PT для футбольного канала
```

Кладёт `<voice>.onnx` и `<voice>.onnx.json` сюда. Для футбольного (PT-PT) сравнить
`pt_PT-tugão-medium`; лёгкий/быстрый вариант — `pt_BR-edresson-low`.

## Платформа: piper ставится только на linux

У `piper-phonemize` (зависимость `piper-tts`) есть wheel'ы под **linux** (CI-раннер
`ubuntu-latest`) и **нет** под **macOS arm64**. Поэтому реальный синтез гоняется на
linux: локально на Mac `tts.synthesize()` вернёт None (fail-open), а полноценный
end-to-end прогон делается через `.github/workflows/reel-smoke.yml` (ручной запуск,
рендерит настоящий Reel и выгружает его артефактом).

## Коммитить бинарь или качать в CI?

По умолчанию `*.onnx` / `*.onnx.json` **в `.gitignore`** — чтобы 60-МБ бинарь не
попал в git случайно. Два пути к рантайму на раннере (решаем в Фазе 1):

1. **Вендоринг**: убрать эти маски из `.gitignore` и закоммитить модель (репо +~30–60 МБ,
   зато полностью офлайн, без сетевого шага).
2. **Загрузка в CI**: качать в шаге workflow (`actions/cache` + download). Возвращает
   сетевой шаг, но git остаётся лёгким.

Пока модели нет — `tts.synthesize()` возвращает `None` (fail-open), и бот работает
как раньше.
