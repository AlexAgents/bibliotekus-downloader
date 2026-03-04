#!/usr/bin/env python3
"""
Bibliotekus Downloader — точка входа.
"""

import os
import sys
import signal
import time
import traceback

from config import OUTPUT_DIR, DELAY_BETWEEN_BOOKS, PROJECT_ROOT, ensure_dirs
from logger import setup_logging, get_logger
from scraper import get_book_links
from downloader import download_book, request_shutdown, is_shutdown_requested
from cli import display_book_list, prompt_selection, print_summary
from utils import prompt_continue, exit_app


def _handle_sigint(signum, frame):
    request_shutdown()


def run_download_session(books, log):
    """
    Одна сессия: показать список → выбрать → скачать.
    Возвращает True если пользователь хочет продолжить.
    """
    import downloader
    downloader._shutdown_requested = False

    downloaded_list, not_downloaded_list = display_book_list(books)

    try:
        selected_indices = prompt_selection(books, not_downloaded_list)
    except (EOFError, KeyboardInterrupt):
        print("\nОтмена.")
        return prompt_continue()

    if not selected_indices:
        print("Отмена.")
        return prompt_continue()

    selected = [(idx, books[idx - 1]) for idx in selected_indices]
    print(f"\n🚀 Скачиваю {len(selected)} книг...")
    print("=" * 70)

    total = len(selected)
    success = fail = 0
    start = time.time()

    for seq, (_, book) in enumerate(selected, 1):
        if is_shutdown_requested():
            log.warning(f"⛔ Остановка. Скачано {success}/{total}.")
            break
        if download_book(book, seq, total):
            success += 1
        else:
            fail += 1
        if seq < total and not is_shutdown_requested():
            time.sleep(DELAY_BETWEEN_BOOKS)

    print_summary(success, fail, (time.time() - start) / 60)

    return prompt_continue()


def main():
    setup_logging()
    log = get_logger()
    signal.signal(signal.SIGINT, _handle_sigint)
    ensure_dirs()

    # Показываем куда будут сохраняться книги
    print(f"📂 Папка проекта: {PROJECT_ROOT}")
    print(f"📚 Книги: {os.path.abspath(OUTPUT_DIR)}")

    # Загружаем список книг
    try:
        books = get_book_links()
    except Exception as e:
        log.error(f"Ошибка загрузки списка: {e}")
        exit_app(1)

    if not books:
        print("Книги не найдены.")
        exit_app(0)

    # Главный цикл
    while True:
        try:
            want_continue = run_download_session(books, log)
            if not want_continue:
                break
            print("\n🔄 Обновляю список...")
            try:
                books = get_book_links()
            except Exception:
                pass
        except KeyboardInterrupt:
            print("\n\n⛔ Прервано.")
            if not prompt_continue():
                break
        except Exception as e:
            log.error(f"Ошибка: {e}")
            traceback.print_exc()
            if not prompt_continue():
                break

    print("\n👋 До свидания!")
    exit_app(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💀 Критическая ошибка: {e}")
        traceback.print_exc()
        exit_app(1)