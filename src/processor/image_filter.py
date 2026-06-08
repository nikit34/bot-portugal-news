import logging
import time

from src.static.settings import NSFW_SCORE_THRESHOLD

logger = logging.getLogger('app')

# Классы детектора nudenet, считающиеся NSFW. Обнажённый мужской торс
# (MALE_BREAST_EXPOSED — частый кадр в футболе: празднования без футболки)
# и любые *_COVERED НЕ блокируем, чтобы не резать легитимный контент.
_UNSAFE_CLASSES = {
    'FEMALE_GENITALIA_EXPOSED',
    'MALE_GENITALIA_EXPOSED',
    'FEMALE_BREAST_EXPOSED',
    'BUTTOCKS_EXPOSED',
    'ANUS_EXPOSED',
}

_detector = None
_checked = 0
_blocked = 0
_elapsed = 0.0


def _get_detector():
    global _detector
    if _detector is None:
        from nudenet import NudeDetector
        _detector = NudeDetector()
        logger.info("[ImageFilter] NudeDetector loaded")
    return _detector


def is_unsafe_image(image_path):
    # Fail-open: любая ошибка детектора (нет зависимости, битый файл и т.п.)
    # не должна ронять публикацию — просто не фильтруем эту картинку.
    global _checked, _blocked, _elapsed
    try:
        started = time.monotonic()
        detections = _get_detector().detect(image_path)
        _elapsed += time.monotonic() - started
    except Exception:
        logger.warning("[ImageFilter] detector unavailable; skipping NSFW check", exc_info=True)
        return False

    _checked += 1
    for detection in detections:
        if detection.get('class') in _UNSAFE_CLASSES and detection.get('score', 0) >= NSFW_SCORE_THRESHOLD:
            _blocked += 1
            logger.debug(f"[ImageFilter] Unsafe image: {detection['class']} {detection['score']:.2f}")
            return True
    return False


def image_filter_summary():
    return (f"[ImageFilter] images checked: {_checked}, blocked NSFW: {_blocked}, "
            f"detector time: {_elapsed:.1f}s")
