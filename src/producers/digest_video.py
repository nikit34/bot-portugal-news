"""Длинный озвученный ДАЙДЖЕСТ-ролик: топ-N новостей дня одним видео.

Зачем. Facebook Content Monetization платит за квалифицированные просмотры, но
ставка резко зависит от формата: длинное видео (in-stream ads) даёт $1-5 за 1000
просмотров против $0.02-0.20 у reels — тот же просмотр стоит в 10-50 раз дороже.
Плюс длинный ролик копит МИНУТЫ ПРОСМОТРА, по которым Meta считает сам допуск в
программу. И, что важнее всего для нашего бота-агрегатора: ролик со своим
сценарием, своим голосом и своей графикой оригинален ПО ПОСТРОЕНИЮ, т.е. не
подпадает под «aggregating / duplicative content» — а именно за это Meta
снимает монетизацию и режет охват всей странице.

Как. На каждый сюжет: плашка 4:5 с заголовком (story_overlay) + TTS-озвучка
(piper) + лёгкий Ken Burns => сегмент .mp4 с ЕДИНЫМИ параметрами кодека. Готовые
сегменты клеятся ffmpeg concat-демуксером без перекодирования (-c copy).

Формат 4:5, а не 9:16, намеренно: вертикаль Meta раскладывает в Reels, а нам
нужен фид-ролик, на котором показываются in-stream ads.

Весь модуль fail-open: нет ffmpeg/piper/голоса, мало сюжетов, слишком короткий
результат или любой сбой => None, и вызывающий просто не публикует дайджест.
"""
import os
import logging
import subprocess

from src.producers.media_uniquify import _ffmpeg_exe
from src.producers import tts
from src.producers.reel import render_reel, _safe_remove
from src.producers.story_overlay import render_headline_story, extract_headline, discard_overlay
from src.static.sources import tmp_folder
from src.static.settings import (
    DIGEST_W,
    DIGEST_H,
    DIGEST_ITEMS,
    DIGEST_MIN_ITEMS,
    DIGEST_TTS_MAX_CHARS,
    DIGEST_MIN_SECONDS,
    DIGEST_MAX_SECONDS,
    DIGEST_SEGMENT_TIMEOUT_SECONDS,
    DIGEST_CONCAT_TIMEOUT_SECONDS,
)

logger = logging.getLogger('app')


def build_digest_video(items, out_mp4=None):
    """Собрать один длинный ролик из items = [{'path': картинка, 'text': текст}].

    Возвращает (путь_к_mp4, [заголовки]) или (None, []) — fail-open. Заголовки
    отдаём наверх, чтобы вызывающий собрал из них описание поста (оно же — причина
    досмотреть, а досмотр это и есть квалифицированный просмотр).
    """
    if not _ffmpeg_exe():
        logger.warning("[digest] no ffmpeg available; skipping digest")
        return None, []
    if not tts.is_available():
        logger.warning("[digest] TTS unavailable (no piper/voice); skipping digest")
        return None, []

    usable = [item for item in (items or [])
              if item.get('path') and os.path.isfile(item['path']) and item.get('text')]
    if len(usable) < DIGEST_MIN_ITEMS:
        logger.info(f"[digest] only {len(usable)} usable item(s) < min {DIGEST_MIN_ITEMS}; skipping")
        return None, []
    usable = usable[:DIGEST_ITEMS]

    segments = []
    headlines = []
    total = 0.0
    try:
        for index, item in enumerate(usable, 1):
            # Бюджет длины: перестаём добавлять сюжеты, как только ролик набрал
            # потолок — лучше 6 сюжетов в рамках, чем 8 с обрезанным хвостом.
            if total >= DIGEST_MAX_SECONDS:
                logger.info(f"[digest] length cap {DIGEST_MAX_SECONDS}s reached at item {index}")
                break
            built = _build_segment(item, index, len(usable),
                                   remaining=DIGEST_MAX_SECONDS - total)
            if not built:
                continue
            path, duration, headline = built
            segments.append(path)
            headlines.append(headline)
            total += duration

        if len(segments) < DIGEST_MIN_ITEMS:
            logger.info(
                f"[digest] only {len(segments)} segment(s) rendered < min {DIGEST_MIN_ITEMS}; skipping")
            return None, []
        if total < DIGEST_MIN_SECONDS:
            # Короткий ролик не тянет на длинное видео — рекламных вставок не будет,
            # а вертикаль такой длины Meta вообще утащит в Reels. Не публикуем.
            logger.info(f"[digest] total {total:.0f}s < min {DIGEST_MIN_SECONDS}s; skipping")
            return None, []

        if out_mp4 is None:
            out_mp4 = os.path.join(tmp_folder, 'digest.mp4')
        if _concat(segments, out_mp4):
            logger.info(f"[digest] built {len(segments)} segments, ~{total:.0f}s -> {out_mp4}")
            return out_mp4, headlines
        return None, []
    except Exception as e:
        logger.warning(f"[digest] build failed: {e}")
        return None, []
    finally:
        for path in segments:
            _safe_remove(path)


def _build_segment(item, index, total_items, remaining):
    """Один сюжет -> (путь_к_сегменту, длительность, заголовок) или None."""
    headline = extract_headline(item['text'])
    if not headline:
        return None

    frame = None
    voice = None
    try:
        # Кикер «2 / 8» даёт зрителю счётчик прогресса — прямой драйвер досмотра,
        # а досмотр это то, за что Facebook в итоге и платит.
        frame = render_headline_story(
            item['path'], headline, brand=f'{index} / {total_items}', size=(DIGEST_W, DIGEST_H))
        if not frame:
            return None
        voice = tts.synthesize(item['text'], max_chars=DIGEST_TTS_MAX_CHARS)
        if not voice:
            return None
        duration = tts.audio_duration(voice)
        if not duration or duration <= 0:
            return None
        duration = min(duration, remaining)
        if duration <= 1:
            return None

        out_path = os.path.join(tmp_folder, f'digest_seg_{index}.mp4')
        rendered = render_reel(
            frame, voice, out_path, motion=True, size=(DIGEST_W, DIGEST_H),
            max_seconds=duration, timeout=DIGEST_SEGMENT_TIMEOUT_SECONDS)
        if not rendered:
            return None
        return rendered, duration, headline
    except Exception as e:
        logger.warning(f"[digest] segment {index} failed: {e}")
        return None
    finally:
        discard_overlay(frame)
        _safe_remove(voice)


def _concat(segments, out_mp4):
    # concat-демуксер вместо filter_complex: сегменты уже собраны с одинаковыми
    # кодеками/частотой/размером, поэтому склейка идёт БЕЗ перекодирования (-c copy)
    # — секунды вместо минут и никакой потери качества на втором проходе.
    list_path = os.path.join(tmp_folder, 'digest_concat.txt')
    try:
        with open(list_path, 'w') as f:
            for path in segments:
                # Одинарные кавычки внутри пути экранируются по правилам ffmpeg concat.
                escaped = os.path.abspath(path).replace("'", r"'\''")
                f.write(f"file '{escaped}'\n")
        cmd = [
            _ffmpeg_exe(), '-y', '-loglevel', 'error',
            '-f', 'concat', '-safe', '0', '-i', list_path,
            '-c', 'copy', '-movflags', '+faststart', out_mp4,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=DIGEST_CONCAT_TIMEOUT_SECONDS)
        if result.returncode != 0 or not os.path.exists(out_mp4):
            logger.warning(
                f"[digest] concat failed (rc={result.returncode}): "
                f"{result.stderr.decode('utf-8', 'replace')[:300]}")
            _safe_remove(out_mp4)
            return False
        return True
    except Exception as e:
        logger.warning(f"[digest] concat failed: {e}")
        _safe_remove(out_mp4)
        return False
    finally:
        _safe_remove(list_path)


def build_digest_caption(title, headlines):
    """Описание поста: заголовок + нумерованный список сюжетов.

    Список — не украшение: он показывает зрителю, что дальше, и удерживает его в
    ролике (Facebook платит за квалифицированные просмотры, а не за показы).
    """
    lines = [title, '']
    lines.extend(f'{i}. {head}' for i, head in enumerate(headlines, 1))
    return '\n'.join(lines)
