"""
Парсинг сайта: список книг, страницы, разрешения.
"""

import re
from bs4 import BeautifulSoup

from config import BASE_URL, REQUEST_TIMEOUT, HEAD_TIMEOUT, PAGE_DETAIL_TIMEOUT
from network import session, safe_head
from logger import get_logger

log = get_logger("scraper")


def get_book_links() -> list[dict]:
    """Список всех книг с главной страницы."""
    log.info("Загружаю главную страницу...")
    resp = session.get(BASE_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    books = []
    for item in soup.select(".books__item"):
        link_tag = item.select_one("a.books__link")
        title_tag = item.select_one("h2.books__title")
        if not (link_tag and title_tag):
            continue
        href = link_tag.get("href", "")
        title = title_tag.get_text(strip=True)
        full_url = BASE_URL + href if href.startswith("/") else href
        slug = href.strip("/").split("/")[-1]
        books.append({"url": full_url, "title": title, "slug": slug, "href": href})

    log.info(f"Найдено книг: {len(books)}")
    return books


def get_page_count_and_images(book_url: str) -> list[dict]:
    """Список страниц книги с миниатюрами."""
    resp = session.get(book_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    pages = []
    for page_div in soup.select("div.book__page"):
        img_tag = page_div.select_one("img.book__thumb")
        page_num_tag = page_div.select_one("span.page-number")
        link_tag = page_div.select_one("a.book__link")
        if not img_tag:
            continue
        pages.append({
            "thumb_src": img_tag.get("src", ""),
            "page_num": int(page_num_tag.get_text(strip=True)) if page_num_tag else None,
            "page_link": link_tag.get("href", "") if link_tag else "",
        })
    return pages


def get_expected_page_count(book_url: str) -> int:
    """Ожидаемое количество страниц. -1 при ошибке."""
    try:
        resp = session.get(book_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return len(soup.select("div.book__page"))
    except Exception as e:
        log.debug(f"Page count error: {e}")
        return -1


def detect_best_resolution(
    book_slug: str, sample_thumb_src: str,
) -> tuple[int | None, str | None]:
    """Определяет максимальное разрешение по миниатюре."""
    filename = sample_thumb_src.split("/")[-1]
    match = re.match(r"^(\d+)-(\d+)(\.(?:jpg|jpeg|png|webp))$", filename, re.IGNORECASE)
    if not match:
        return None, None

    page_idx = match.group(1)
    ext = match.group(3)
    dir_path = "/".join(sample_thumb_src.split("/")[:-1])

    for res in [2400, 1600, 1200, 800]:
        url = BASE_URL + f"{dir_path}/{page_idx}-{res}{ext}"
        resp = safe_head(url, timeout=HEAD_TIMEOUT)
        if resp and resp.status_code == 200:
            cl = int(resp.headers.get("Content-Length", 0))
            if cl > 1000:
                return res, ext

    return 400, ext


def detect_individual_page_resolution(
    book_slug: str, page_link: str,
) -> str | None:
    """Ищет URL картинки макс. разрешения на странице разворота."""
    if not page_link:
        return None

    url = BASE_URL + page_link if page_link.startswith("/") else page_link
    try:
        resp = session.get(url, timeout=PAGE_DETAIL_TIMEOUT)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        for img in soup.select("img"):
            src = img.get("src", "")
            if book_slug in src and "-400" not in src:
                return src

        for img in soup.select("img"):
            for attr in ("srcset", "data-src", "data-original"):
                val = img.get(attr, "")
                if book_slug in val:
                    return val.split(",")[-1].strip().split(" ")[0]

        for source in soup.select("source"):
            srcset = source.get("srcset", "")
            if book_slug in srcset:
                return srcset.split(",")[-1].strip().split(" ")[0]

        for img in soup.select("img"):
            src = img.get("src", "")
            if book_slug in src:
                return src
    except Exception as e:
        log.debug(f"Individual resolution error: {e}")

    return None