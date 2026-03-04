"""
Оптимизация изображений: качество, ресайз, конвертация.
"""

import os
from io import BytesIO
from PIL import Image

import config
from logger import get_logger

log = get_logger("optimizer")


def calculate_optimal_settings(
    page_count: int,
    total_raw_size_kb: float,
    avg_width: int,
    avg_height: int,
) -> tuple[int, int]:
    """
    Подбирает (jpeg_quality, max_dimension).
    max_dimension=0 — без ресайза.
    """
    target_bytes = config.TARGET_PDF_MB * 1024 * 1024
    total_raw_bytes = total_raw_size_kb * 1024

    if total_raw_bytes == 0 or page_count == 0:
        return config.MAX_JPEG_QUALITY, 0

    compression_needed = total_raw_bytes / target_bytes
    if compression_needed <= 1.0:
        return config.MAX_JPEG_QUALITY, 0

    max_dim = max(avg_width, avg_height)

    if compression_needed > 4.0 and max_dim > 3000:
        resize_to, quality = 1800, max(config.MIN_JPEG_QUALITY, 82)
    elif compression_needed > 3.0 and max_dim > 2500:
        resize_to, quality = 2000, max(config.MIN_JPEG_QUALITY, 83)
    elif compression_needed > 2.0 and max_dim > 2000:
        resize_to, quality = 0, max(config.MIN_JPEG_QUALITY, 80)
    elif compression_needed > 1.5:
        resize_to, quality = 0, max(config.MIN_JPEG_QUALITY, 82)
    else:
        resize_to, quality = 0, config.MAX_JPEG_QUALITY

    if resize_to > 0 and max_dim <= config.MIN_PAGE_DIMENSION:
        return config.MAX_JPEG_QUALITY, 0
    if resize_to > 0 and resize_to < config.MIN_PAGE_DIMENSION:
        resize_to = config.MIN_PAGE_DIMENSION

    return quality, resize_to


def smart_optimize_image(
    img_data: bytes,
    jpeg_quality: int,
    max_dimension: int,
) -> tuple[bytes, int, int]:
    """Оптимизирует одно изображение. Возвращает (bytes, orig_w, orig_h)."""
    try:
        img = Image.open(BytesIO(img_data))
        orig_w, orig_h = img.size

        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        max_orig = max(orig_w, orig_h)

        if max_orig <= config.MIN_PAGE_DIMENSION:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=config.MAX_JPEG_QUALITY, optimize=True)
            result = buf.getvalue()
            img.close()
            return (result if len(result) < len(img_data) else img_data, orig_w, orig_h)

        if max_dimension > 0 and max_orig > max_dimension:
            ratio = max_dimension / max_orig
            if ratio < 0.9:
                img = img.resize((int(orig_w * ratio), int(orig_h * ratio)), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        result = buf.getvalue()
        img.close()
        return (result if len(result) < len(img_data) else img_data, orig_w, orig_h)

    except Exception as e:
        log.debug(f"Optimize error: {e}")
        return img_data, 0, 0


def optimize_and_save_page(args: tuple) -> tuple:
    """Обёртка для многопоточности."""
    page_idx, raw_path, jpeg_quality, max_dimension, temp_dir = args
    try:
        with open(raw_path, "rb") as f:
            img_data = f.read()

        opt_data, w, h = smart_optimize_image(img_data, jpeg_quality, max_dimension)

        opt_path = os.path.join(temp_dir, f"page_{page_idx:04d}.jpg")
        with open(opt_path, "wb") as f:
            f.write(opt_data)

        try:
            os.remove(raw_path)
        except OSError:
            pass

        return page_idx, opt_path, len(img_data), len(opt_data), w, h
    except Exception:
        return page_idx, None, 0, 0, 0, 0