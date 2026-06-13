import logging
import time
import threading

from PIL import Image

from src.static.settings import NSFW_SCORE_THRESHOLD, IMAGE_MIN_WIDTH, IMAGE_MIN_HEIGHT

logger = logging.getLogger('app')

# is_unsafe_image now runs via asyncio.to_thread (off the event loop), so several
# worker threads can hit it in parallel. This lock guards the one-time detector init
# (so we don't build several NudeDetectors) and the shared counters (so increments
# aren't lost). The expensive detect() runs OUTSIDE the lock — onnxruntime handles
# concurrent inference on one session, and we don't want to serialise it.
_lock = threading.Lock()
_low_quality = 0


def is_low_quality_image(image_path):
    # Reject tiny thumbnails (e.g. UOL's 142x100 feed previews) that look bad in the
    # feed. Reads only the image header, so it's cheap. Fail-open: if the size can't
    # be read, don't filter (don't drop a possibly-fine image).
    global _low_quality
    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception:
        logger.warning("[ImageFilter] could not read image size; skipping quality check", exc_info=True)
        return False

    if width < IMAGE_MIN_WIDTH or height < IMAGE_MIN_HEIGHT:
        _low_quality += 1
        logger.debug(
            f"[ImageFilter] low-quality image {width}x{height} "
            f"(min {IMAGE_MIN_WIDTH}x{IMAGE_MIN_HEIGHT})")
        return True
    return False

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
    # Double-checked locking: avoid taking the lock on the hot path once loaded,
    # but ensure only one thread constructs the (heavy) detector.
    if _detector is None:
        with _lock:
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
        elapsed = time.monotonic() - started
    except Exception:
        logger.warning("[ImageFilter] detector unavailable; skipping NSFW check", exc_info=True)
        return False

    unsafe = any(
        detection.get('class') in _UNSAFE_CLASSES and detection.get('score', 0) >= NSFW_SCORE_THRESHOLD
        for detection in detections)
    with _lock:  # increments run on worker threads — guard against lost updates
        _checked += 1
        _elapsed += elapsed
        if unsafe:
            _blocked += 1
    if unsafe:
        logger.debug("[ImageFilter] Unsafe image blocked")
    return unsafe


def image_filter_summary():
    return (f"[ImageFilter] images checked: {_checked}, blocked NSFW: {_blocked}, "
            f"low-quality filtered: {_low_quality}, detector time: {_elapsed:.1f}s")
