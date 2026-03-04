"""
Интерфейс: список книг, выбор, настройка качества, статистика.
"""

import os
import re

import config
from config import OUTPUT_DIR, QUALITY_PRESETS, apply_preset, apply_custom_settings
from utils import get_pdf_path, is_downloaded
from logger import get_logger

log = get_logger("cli")


# ═══════════════════════════════════════════════
# Настройка качества
# ═══════════════════════════════════════════════

def quality_settings_menu() -> None:
    """Интерактивное меню настройки качества."""
    while True:
        print(f"\n{'═' * 60}")
        print("  ⚙  НАСТРОЙКА КАЧЕСТВА")
        print(f"{'═' * 60}")

        print(f"\n  Текущие: {config.get_current_settings_str()}")

        print(f"\n  {'─' * 56}")
        print(f"  {'Пресет':<10} {'Название':<14} {'PDF МБ':>7} "
              f"{'JPEG %':>10} {'Мин.px':>7}  Описание")
        print(f"  {'─' * 56}")

        for key, p in QUALITY_PRESETS.items():
            marker = " ◄" if (
                config.TARGET_PDF_MB == p["target_pdf_mb"]
                and config.MIN_JPEG_QUALITY == p["min_jpeg_quality"]
            ) else ""
            print(
                f"  {key:<10} {p['name']:<14} {p['target_pdf_mb']:>5}   "
                f"{p['min_jpeg_quality']}-{p['max_jpeg_quality']:>2}   "
                f"{p['min_page_dimension']:>5}   "
                f"{p['desc']}{marker}"
            )

        print(f"  {'─' * 56}")
        print(f"  custom    Ввести свои значения")
        print(f"  back      Назад к выбору книг")
        print(f"  {'─' * 56}")

        choice = input("\n  Выберите пресет: ").strip().lower()

        if choice in ("back", "b", ""):
            return

        if choice in QUALITY_PRESETS:
            apply_preset(choice)
            p = QUALITY_PRESETS[choice]
            print(f"\n  ✅ Применён пресет «{p['name']}»")
            print(f"     {config.get_current_settings_str()}")
            return

        if choice == "custom":
            _custom_settings_input()
            return

        print("  ⚠ Неизвестный пресет")


def _custom_settings_input() -> None:
    """Ввод пользовательских значений."""
    print(f"\n  📝 Введите значения (Enter — оставить текущее):")
    print(f"     Чем больше МБ и выше %, тем лучше качество\n")

    target = _input_int(
        f"  Целевой размер PDF, МБ [{config.TARGET_PDF_MB}]: ",
        config.TARGET_PDF_MB, 5, 9999,
    )
    min_q = _input_int(
        f"  Мин. JPEG качество, % [{config.MIN_JPEG_QUALITY}]: ",
        config.MIN_JPEG_QUALITY, 30, 98,
    )
    max_q = _input_int(
        f"  Макс. JPEG качество, % [{config.MAX_JPEG_QUALITY}]: ",
        config.MAX_JPEG_QUALITY, min_q, 99,
    )
    min_dim = _input_int(
        f"  Мин. разрешение, px [{config.MIN_PAGE_DIMENSION}]: ",
        config.MIN_PAGE_DIMENSION, 400, 2400,
    )

    apply_custom_settings(target, min_q, max_q, min_dim)
    print(f"\n  ✅ Применены настройки:")
    print(f"     {config.get_current_settings_str()}")


def _input_int(prompt: str, default: int, min_val: int, max_val: int) -> int:
    """Ввод числа с валидацией."""
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return default
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"    ⚠ Допустимо: {min_val}–{max_val}")
        except ValueError:
            print(f"    ⚠ Введите число")


# ═══════════════════════════════════════════════
# Список книг
# ═══════════════════════════════════════════════

def display_book_list(books: list[dict]) -> tuple[list, list]:
    """Выводит список книг со статусами."""
    downloaded_list = []
    not_downloaded_list = []

    for i, book in enumerate(books, 1):
        if is_downloaded(book):
            size = os.path.getsize(get_pdf_path(book)) / (1024 * 1024)
            downloaded_list.append((i, book, size))
        else:
            not_downloaded_list.append((i, book))

    print("\n" + "=" * 70)
    print("СПИСОК КНИГ")
    print("=" * 70)

    for i, book in enumerate(books, 1):
        if is_downloaded(book):
            size = os.path.getsize(get_pdf_path(book)) / (1024 * 1024)
            status = f"✅ {size:6.1f}M"
        else:
            status = "⬜       "

        short = book["title"][:42] + "..." if len(book["title"]) > 45 else book["title"]
        print(f"  {i:3d}. {status}  {short}")

    print("=" * 70)
    print(
        f"\n📊 Всего: {len(books)} | "
        f"Скачано: {len(downloaded_list)} | "
        f"Осталось: {len(not_downloaded_list)}"
    )

    if downloaded_list:
        total_size = sum(d[2] for d in downloaded_list)
        print(f"   Размер: {total_size:.1f} МБ ({total_size / 1024:.2f} ГБ)")

    if not_downloaded_list and len(not_downloaded_list) <= 30:
        print("\n   Нескачанные:")
        for num, book in not_downloaded_list:
            print(f"     {num:3d}. {book['title'][:55]}")

    print(f"\n⚙ {config.get_current_settings_str()}")

    return downloaded_list, not_downloaded_list


# ═══════════════════════════════════════════════
# Выбор книг
# ═══════════════════════════════════════════════

def parse_selection(answer: str, total_books: int) -> list[int]:
    """Парсит ввод: y, n, номера, диапазоны."""
    answer = answer.strip().lower()

    if answer in ("n", "q", "quit", "exit"):
        return []
    if answer in ("y", ""):
        return list(range(1, total_books + 1))

    numbers = set()
    for part in answer.replace(" ", "").split(","):
        m = re.match(r"^(\d+)\s*-\s*(\d*)$", part)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else total_books
            numbers.update(range(max(1, start), min(end, total_books) + 1))
        else:
            try:
                n = int(part)
                if 1 <= n <= total_books:
                    numbers.add(n)
            except ValueError:
                pass

    return sorted(numbers)


def prompt_selection(
    books: list[dict],
    not_downloaded_list: list[tuple],
) -> list[int]:
    """Главное меню выбора с настройкой качества."""
    while True:
        print(
            "\n📝 Команды:"
            "\n   y — все книги | new — нескачанные | n — отмена"
            "\n   5 | 1,3,5 | 5-20 | 5- | 1-10,15,20-"
            "\n   settings — настройка качества"
        )

        answer = input("\nЧто скачать? ").strip()

        if answer.lower() in ("settings", "s", "set", "quality", "q"):
            quality_settings_menu()
            print(f"\n⚙ {config.get_current_settings_str()}")
            continue

        if answer.lower() == "new":
            selected = [item[0] for item in not_downloaded_list]
            if not selected:
                print("✅ Все книги уже скачаны!")
                return []
            print(f"\nБудет скачано {len(selected)} книг")
            return selected

        return parse_selection(answer, len(books))


# ═══════════════════════════════════════════════
# Итоги
# ═══════════════════════════════════════════════

def print_summary(
    success_count: int,
    fail_count: int,
    elapsed_minutes: float,
) -> None:
    """Итоговая статистика."""
    total_size_mb = sum(
        os.path.getsize(os.path.join(OUTPUT_DIR, f)) / (1024 * 1024)
        for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf")
    )
    file_count = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf")])

    print(f"\n{'=' * 70}")
    print(f"🏁 ГОТОВО за {elapsed_minutes:.1f} мин!")
    print(f"   ✅ {success_count} | ❌ {fail_count}")
    print(f"   📁 {file_count} файлов, {total_size_mb / 1024:.2f} ГБ")
    print(f"   📂 {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 70)