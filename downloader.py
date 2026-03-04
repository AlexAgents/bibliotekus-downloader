"""
Скачивание книг: загрузка страниц, оптимизация, сборка PDF.
"""

import os
import re
import time
import shutil
import tempfile
import concurrent.futures

from PIL import Image

from config import BASE_URL, MAX_WORKERS_PAGES, IMAGE_TIMEOUT
from network import session
from logger import get_logger
from utils import get_pdf_path
from scraper import (
    get_page_count_and_images,
    detect_best_resolution,
    detect_individual_page_resolution,
)
from image_optimizer import calculate_optimal_settings, optimize_and_save_page
from pdf_builder import build_pdf_from_files

log = get_logger("downloader")

_shutdown_requested = False


def request_shutdown():
    global _shutdown_requested
    _shutdown_requested = True
    log.warning("\n⛔ Остановка. Завершаю текущую книгу...")


def is_shutdown_requested() -> bool:
    return _shutdown_requested


# ─── Загрузка страниц ────────────────────────────────────────────────

def _try_download(url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=IMAGE_TIMEOUT)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.content
    except Exception:
        pass
    return None


def _try_individual_pattern(pattern: str, page_num_str: str) -> bytes | None:
    try:
        parts = pattern.split("/")
        ind_filename = parts[-1]
        m = re.match(r"^(\d+)(.*)(\.(?:jpg|jpeg|png|webp))$", ind_filename, re.IGNORECASE)
        if not m:
            return None
        suffix, ind_ext = m.group(2), m.group(3)
        new_url = "/".join(parts[:-1]) + f"/{page_num_str}{suffix}{ind_ext}"
        if not new_url.startswith("http"):
            new_url = BASE_URL + new_url
        return _try_download(new_url)
    except Exception:
        return None


def _download_single_page(args: tuple) -> tuple[int, str | None, int]:
    (page_idx, thumb_src, best_res, ext, dir_path,
     individual_pattern, book_slug, temp_dir) = args

    img_data = None
    filename = thumb_src.split("/")[-1]
    match = re.match(r"^(\d+)-(\d+)(\.(?:jpg|jpeg|png|webp))$", filename, re.IGNORECASE)

    if match:
        page_num_str = match.group(1)
        file_ext = match.group(3)

        if individual_pattern:
            img_data = _try_individual_pattern(individual_pattern, page_num_str)
        if not img_data and best_res:
            img_data = _try_download(BASE_URL + f"{dir_path}/{page_num_str}-{best_res}{file_ext}")
        if not img_data:
            img_data = _try_download(BASE_URL + thumb_src)
    else:
        img_data = _try_download(BASE_URL + thumb_src)

    if img_data:
        temp_path = os.path.join(temp_dir, f"page_{page_idx:04d}.raw")
        with open(temp_path, "wb") as f:
            f.write(img_data)
        return page_idx, temp_path, len(img_data)
    return page_idx, None, 0


def _sample_dimensions(raw_pages: dict, count: int = 5) -> tuple[int, int]:
    avg_w, avg_h, samples = 0, 0, 0
    for idx in sorted(raw_pages.keys())[:count]:
        try:
            img = Image.open(raw_pages[idx][0])
            avg_w += img.size[0]
            avg_h += img.size[1]
            img.close()
            samples += 1
        except Exception:
            pass
    return (avg_w // samples, avg_h // samples) if samples else (0, 0)


def _download_all_pages(pages, best_res, ext, dir_path,
                        individual_pattern, slug, temp_dir, page_count):
    tasks = [
        (i, p["thumb_src"], best_res, ext, dir_path,
         individual_pattern, slug, temp_dir)
        for i, p in enumerate(pages)
    ]

    raw_pages = {}
    downloaded = failed = 0
    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_PAGES) as ex:
        futures = {ex.submit(_download_single_page, t): t[0] for t in tasks}
        for future in concurrent.futures.as_completed(futures):
            if _shutdown_requested:
                ex.shutdown(wait=False, cancel_futures=True)
                break
            try:
                idx, path, size = future.result()
                if path:
                    raw_pages[idx] = (path, size)
                    downloaded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

            done = downloaded + failed
            if done % 20 == 0 or done == page_count:
                elapsed = time.time() - start
                speed = done / elapsed if elapsed > 0 else 0
                log.info(f"  ⬇ {done}/{page_count} [{speed:.1f}/с]")

    return raw_pages, time.time() - start


def _optimize_all_pages(raw_pages, quality, max_dim, temp_dir):
    tasks = [
        (idx, raw_pages[idx][0], quality, max_dim, temp_dir)
        for idx in sorted(raw_pages.keys())
    ]
    opt_pages = {}
    total_orig = total_opt = 0
    workers = min(os.cpu_count() or 4, 8)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for result in ex.map(optimize_and_save_page, tasks):
            idx, path, orig, opt, w, h = result
            if path:
                opt_pages[idx] = path
                total_orig += orig
                total_opt += opt

    return opt_pages, total_orig / (1024**2), total_opt / (1024**2)


# ─── Основная функция ────────────────────────────────────────────────

def download_book(book_info: dict, index: int, total: int) -> bool:
    if _shutdown_requested:
        return False

    title = book_info["title"]
    slug = book_info["slug"]
    pdf_path = get_pdf_path(book_info)

    if os.path.exists(pdf_path):
        log.info(f"[{index}/{total}] ⏭ Пропуск: {title} [{slug}]")
        return True

    log.info(f"\n[{index}/{total}] 📖 {title}")
    log.info(f"  🔗 {slug}")

    temp_dir = tempfile.mkdtemp(prefix=f"book_{slug}_")
    try:
        return _process_book(book_info, pdf_path, temp_dir)
    except KeyboardInterrupt:
        request_shutdown()
        return False
    except Exception as e:
        log.error(f"  ❌ {e}")
        log.debug("Traceback:", exc_info=True)
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _process_book(book_info, pdf_path, temp_dir):
    slug = book_info["slug"]
    start_time = time.time()

    pages = get_page_count_and_images(book_info["url"])
    if not pages:
        log.warning("  ⚠ Страницы не найдены!")
        return False

    page_count = len(pages)
    log.info(f"  📄 {page_count} страниц")

    first_thumb = pages[0]["thumb_src"]
    best_res, ext = detect_best_resolution(slug, first_thumb)
    log.info(f"  🔍 {best_res}px")

    individual_pattern = None
    if pages[0]["page_link"]:
        individual_pattern = detect_individual_page_resolution(slug, pages[0]["page_link"])

    dir_path = "/".join(first_thumb.split("/")[:-1])

    raw_pages, dl_time = _download_all_pages(
        pages, best_res, ext, dir_path,
        individual_pattern, slug, temp_dir, page_count,
    )

    if _shutdown_requested or not raw_pages:
        if not raw_pages:
            log.error("  ❌ Ничего не скачано")
        return False

    total_raw_kb = sum(s for _, s in raw_pages.values()) / 1024
    avg_w, avg_h = _sample_dimensions(raw_pages)
    log.info(f"  📊 {total_raw_kb / 1024:.1f} МБ | {avg_w}×{avg_h}")

    quality, max_dim = calculate_optimal_settings(len(raw_pages), total_raw_kb, avg_w, avg_h)
    resize_info = f"→{max_dim}px" if max_dim > 0 else "без ресайза"
    log.info(f"  🎛 JPEG {quality}%, {resize_info}")

    opt_pages, orig_mb, opt_mb = _optimize_all_pages(raw_pages, quality, max_dim, temp_dir)
    savings = (1 - opt_mb / orig_mb) * 100 if orig_mb > 0 else 0
    log.info(f"  📉 {orig_mb:.1f} → {opt_mb:.1f} МБ (-{savings:.0f}%)")

    ordered = [opt_pages.get(i) for i in range(page_count) if i in opt_pages]
    if not ordered:
        log.error("  ❌ Нет страниц для PDF")
        return False

    log.info(f"  📝 PDF ({len(ordered)} стр)...")
    success = build_pdf_from_files(ordered, pdf_path)

    if success:
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        log.info(f"  ✅ {size_mb:.1f} МБ | {time.time() - start_time:.1f}с")
        return True

    log.error("  ❌ Ошибка сборки PDF")
    return False