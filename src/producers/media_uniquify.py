import os
import time
import random
import shutil
import logging
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps

from src.static.sources import tmp_folder
from src.static.settings import (
    UNIQUIFY_ENABLED,
    UNIQUIFY_IMAGE_ENABLED,
    UNIQUIFY_VIDEO_ENABLED,
    WATERMARK_ENABLED,
    WATERMARK_TEXT,
    WATERMARK_OPACITY,
    VIDEO_UNIQUIFY_TIMEOUT_SECONDS,
    UNIQUIFY_VIDEO_MAX_DIM,
)

logger = logging.getLogger('app')

# DejaVu Sans зашит в репо — системных шрифтов на CI нет; полное покрытие пт-диакритики.
_FONT_BOLD = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'fonts', 'DejaVuSans-Bold.ttf')


# --- общее -------------------------------------------------------------------

def _handle_from_url(url):
    # 'https://t.me/sportportugal' -> '@sportportugal'
    if not url:
        return ''
    slug = url.rstrip('/').split('/')[-1].lstrip('@')
    return ('@' + slug) if slug else ''


def resolve_watermark_text(context):
    # Явный WATERMARK_TEXT приоритетнее; иначе @handle нашего телеграм-канала.
    return WATERMARK_TEXT or _handle_from_url((context or {}).get('self_telegram_channel', ''))


def _jitter(lo, hi):
    return random.uniform(lo, hi)


def _ffmpeg_exe():
    # Бинарь из imageio-ffmpeg (ставится pip-ом, работает в CI без apt); если нет —
    # системный ffmpeg из PATH. None => видео-уникализацию пропускаем (fail-open).
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which('ffmpeg')


# --- картинки (Pillow) -------------------------------------------------------

def _draw_image_watermark(img, text):
    w, h = img.size
    font_size = max(18, w // 28)
    font = ImageFont.truetype(_FONT_BOLD, font_size)
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = max(12, font_size // 2)
    x = w - tw - margin - bbox[0]
    y = h - th - margin - bbox[1]
    alpha = int(255 * WATERMARK_OPACITY)
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, int(alpha * 0.8)))  # тень
    draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))
    return Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')


def uniquify_image(src_path, watermark_text):
    """Брендирует + слегка меняет картинку. Возвращает путь к новому .jpg или None.

    Срез EXIF + лёгкий кроп + джиттер яркости/контраста/цвета/резкости + ре-энкод
    в JPEG со случайным quality сдвигают перцептивный хэш относительно оригинала;
    вотермарка с именем канала добавляет видимый бренд.
    """
    try:
        with Image.open(src_path) as raw:
            img = ImageOps.exif_transpose(raw).convert('RGB')

        w, h = img.size
        dx = int(w * _jitter(0.005, 0.025))
        dy = int(h * _jitter(0.005, 0.025))
        if w - 2 * dx > 10 and h - 2 * dy > 10:
            img = img.crop((dx, dy, w - dx, h - dy))

        img = ImageEnhance.Brightness(img).enhance(_jitter(0.95, 1.05))
        img = ImageEnhance.Contrast(img).enhance(_jitter(0.95, 1.05))
        img = ImageEnhance.Color(img).enhance(_jitter(0.94, 1.07))
        img = ImageEnhance.Sharpness(img).enhance(_jitter(0.90, 1.15))

        if WATERMARK_ENABLED and watermark_text:
            img = _draw_image_watermark(img, watermark_text)

        out_path = os.path.splitext(src_path)[0] + '.uniq.jpg'
        # без exif= при save() метаданные не переносятся => EXIF срезан
        img.save(out_path, format='JPEG', quality=random.randint(86, 93), optimize=True)
        return out_path
    except Exception as e:
        logger.warning(f"[uniquify] image failed for {src_path}: {e}")
        return None


# --- видео (ffmpeg) ----------------------------------------------------------

def _make_watermark_png(text):
    # Рендерим вотермарку как отдельный PNG (Pillow) и накладываем overlay-фильтром —
    # так не нужен drawtext/freetype в сборке ffmpeg (статик-бинарь его часто не имеет).
    font_size = 40
    font = ImageFont.truetype(_FONT_BOLD, font_size)
    probe = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    bbox = probe.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 16
    png = Image.new('RGBA', (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    draw = ImageDraw.Draw(png)
    draw.rounded_rectangle([0, 0, png.width - 1, png.height - 1], radius=12, fill=(0, 0, 0, 120))
    draw.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=(255, 255, 255, 235))
    path = tmp_folder + '/' + str(time.time_ns()) + '.wm.png'
    png.save(path)
    return path


def _video_vf():
    # Лёгкий джиттер + 2px-кроп со сдвигом кадра + (опц.) потолок разрешения + чётные
    # размеры под yuv420p.
    eq = (f"eq=brightness={_jitter(-0.04, 0.04):.3f}:"
          f"contrast={_jitter(0.95, 1.05):.3f}:saturation={_jitter(0.92, 1.08):.3f}")
    parts = [eq, "crop=in_w-4:in_h-4:2:2"]
    # Ограничиваем длинную сторону до UNIQUIFY_VIDEO_MAX_DIM (force_original_aspect_ratio
    # =decrease вписывает в бокс, min(...) не даёт апскейлить мелкие клипы). Дёшево
    # ре-энкодит крупные 200-МБ клипы и режет размер аплоуда. 0 => без потолка.
    if UNIQUIFY_VIDEO_MAX_DIM and UNIQUIFY_VIDEO_MAX_DIM > 0:
        m = UNIQUIFY_VIDEO_MAX_DIM
        parts.append(
            f"scale='min({m},iw)':'min({m},ih)':force_original_aspect_ratio=decrease")
    parts.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
    return ",".join(parts)


def uniquify_video(src_path, watermark_text):
    """Ре-энкодит видео с джиттером/кропом/вотермаркой и срезом метаданных через
    ffmpeg. Возвращает путь к новому .mp4 или None (fail-open: при любой проблеме
    публикуется оригинал)."""
    exe = _ffmpeg_exe()
    if not exe:
        logger.warning("[uniquify] no ffmpeg available; skipping video uniquify")
        return None

    wm_png = None
    out_path = os.path.splitext(src_path)[0] + '.uniq.mp4'
    try:
        if WATERMARK_ENABLED and watermark_text:
            wm_png = _make_watermark_png(watermark_text)

        cmd = [exe, '-y', '-loglevel', 'error', '-i', src_path]
        if wm_png:
            cmd += ['-i', wm_png,
                    '-filter_complex',
                    f"[0:v]{_video_vf()}[base];[base][1:v]overlay=W-w-20:H-h-20[v]",
                    '-map', '[v]', '-map', '0:a?']
        else:
            cmd += ['-vf', _video_vf(), '-map', '0:v', '-map', '0:a?']
        cmd += ['-map_metadata', '-1',
                '-c:v', 'libx264', '-crf', str(random.randint(23, 26)),
                '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', out_path]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=VIDEO_UNIQUIFY_TIMEOUT_SECONDS)
        if result.returncode != 0 or not os.path.exists(out_path):
            logger.warning(
                f"[uniquify] ffmpeg failed (rc={result.returncode}): "
                f"{result.stderr.decode('utf-8', 'replace')[:300]}")
            if os.path.exists(out_path):
                os.remove(out_path)
            return None
        return out_path
    except Exception as e:
        logger.warning(f"[uniquify] video failed for {src_path}: {e}")
        if os.path.exists(out_path):
            os.remove(out_path)
        return None
    finally:
        if wm_png and os.path.exists(wm_png):
            try:
                os.remove(wm_png)
            except OSError:
                pass


# --- точка входа для serve() -------------------------------------------------

def apply_uniquify(url_path, is_video, context):
    """Мутирует url_path: заменяет 'path' на брендированный/уникализированный файл и
    обнуляет 'url', чтобы Instagram чеканил image_url из обработанного ЛОКАЛЬНОГО
    файла, а не постил оригинальную публичную ссылку источника. No-op при выключенном
    флаге или сбое (тогда публикуется оригинал)."""
    if not UNIQUIFY_ENABLED:
        return
    src_path = url_path.get('path')
    if not src_path or not os.path.exists(src_path):
        return

    watermark_text = resolve_watermark_text(context)
    if is_video:
        new_path = uniquify_video(src_path, watermark_text) if UNIQUIFY_VIDEO_ENABLED else None
    else:
        new_path = uniquify_image(src_path, watermark_text) if UNIQUIFY_IMAGE_ENABLED else None

    if new_path and new_path != src_path and os.path.exists(new_path):
        try:
            os.remove(src_path)
        except OSError:
            pass
        url_path['path'] = new_path
        url_path['url'] = None
        logger.debug(f"[uniquify] media branded/uniquified -> {os.path.basename(new_path)}")
