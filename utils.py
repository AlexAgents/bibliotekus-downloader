"""
Утилиты: имена файлов, пути, форматирование, управление выходом.
"""

import os
import re
import sys

from config import OUTPUT_DIR


# ═══════════════════════════════════════════════
# Работа с именами файлов
# ═══════════════════════════════════════════════

def sanitize_filename(name: str) -> str:
    """Убирает недопустимые символы из имени файла."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:200]


def get_pdf_filename(book: dict) -> str:
    """Формат: 'Название [slug].pdf' — slug уникален."""
    title = sanitize_filename(book["title"])
    slug = book["slug"]
    max_len = 180 - len(slug)
    if max_len < 20:
        max_len = 20
    if len(title) > max_len:
        title = title[:max_len].rstrip()
    return f"{title} [{slug}].pdf"


def get_old_filename(book: dict) -> str:
    """Старый формат без slug."""
    return sanitize_filename(book["title"]) + ".pdf"


def get_pdf_path(book: dict) -> str:
    """Полный путь к PDF."""
    return os.path.join(OUTPUT_DIR, get_pdf_filename(book))


def is_downloaded(book: dict) -> bool:
    """Скачана ли книга."""
    return os.path.exists(get_pdf_path(book))


# ═══════════════════════════════════════════════
# Форматирование
# ═══════════════════════════════════════════════

def format_size(size_bytes: int | float) -> str:
    """Человекочитаемый размер."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} МБ"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} ГБ"


def make_ranges(numbers: list[int]) -> str:
    """[1,2,3,5,7,8,9] → '1-3,5,7-9'"""
    if not numbers:
        return ""
    numbers = sorted(set(numbers))
    ranges = []
    start = end = numbers[0]
    for n in numbers[1:]:
        if n == end + 1:
            end = n
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = n
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ",".join(ranges)


# ═══════════════════════════════════════════════
# Управление выходом
# ═══════════════════════════════════════════════

def prompt_continue() -> bool:
    """
    Универсальный промт после завершения любого действия.

    Enter → вернуться в меню (True)
    q     → выйти (False)
    """
    print()
    print("─" * 50)
    try:
        answer = input("  ⏎ Enter — в меню | q — выйти: ").strip().lower()
        return answer not in ("q", "quit", "exit", "й", "выход")
    except (EOFError, KeyboardInterrupt):
        return False


def exit_app(code: int = 0):
    """
    Завершение приложения с паузой.
    Всегда даёт пользователю прочитать вывод перед закрытием окна.
    """
    print()
    print("═" * 50)
    try:
        input("  ⏎ Нажмите Enter для выхода...")
    except (EOFError, KeyboardInterrupt):
        pass

    sys.exit(code)