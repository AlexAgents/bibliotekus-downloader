"""
Все настройки проекта.
Значения качества могут быть изменены через меню.
"""

import os
import sys


# ═══════════════════════════════════════════════
# Определение корневой папки
# ═══════════════════════════════════════════════

def _get_root_dir() -> str:
    """
    Определяет корневую папку проекта.
    
    - EXE (PyInstaller):  папка где лежит .exe файл
    - Обычный запуск:     папка где лежит config.py
    
    Это критически важно: data/ должна создаваться
    РЯДОМ с exe, а не во временной папке PyInstaller.
    """
    if getattr(sys, "frozen", False):
        # Запущены как EXE — берём папку где лежит .exe
        return os.path.dirname(sys.executable)
    else:
        # Обычный запуск — папка где лежит config.py
        return os.path.dirname(os.path.abspath(__file__))


# === Пути ===
PROJECT_ROOT = _get_root_dir()
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# === URL ===
BASE_URL = "https://bibliotekus.artlebedev.ru"

# === Версия ===
VERSION = "1.0.0"

# === Директория для книг ===
OUTPUT_DIR = os.environ.get(
    "BIBLIOTEKUS_OUTPUT",
    os.path.join(DATA_DIR, "books_pdf"),
)

# === Иконки ===
ICON_MAIN = os.path.join(ASSETS_DIR, "icon.ico")
ICON_VERIFY = os.path.join(ASSETS_DIR, "icon-verify.ico")
ICON_PATH = ICON_MAIN

# === Точка входа ===
# Для сборки EXE — определяем какой файл использовать
_source_dir = os.path.dirname(os.path.abspath(__file__))
ENTRY_POINT = os.path.join(_source_dir, "__main__.py")
if not os.path.exists(ENTRY_POINT):
    ENTRY_POINT = os.path.join(_source_dir, "main.py")

# === Параллелизм ===
MAX_WORKERS_PAGES = 12
DELAY_BETWEEN_BOOKS = 0.5

# === Качество PDF (изменяемые через меню) ===
TARGET_PDF_MB = 80
MIN_PAGE_DIMENSION = 1200
MIN_JPEG_QUALITY = 78
MAX_JPEG_QUALITY = 92

# === HTTP ===
REQUEST_TIMEOUT = 30
HEAD_TIMEOUT = 10
PAGE_DETAIL_TIMEOUT = 15
IMAGE_TIMEOUT = 20
MAX_RETRIES = 3
RETRY_BACKOFF = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
}

POOL_CONNECTIONS = 20
POOL_MAXSIZE = 20

# === Логирование ===
LOG_FILE = os.path.join(DATA_DIR, "bibliotekus.log")
LOG_LEVEL = "INFO"

# === Пресеты качества ===
QUALITY_PRESETS = {
    "low": {
        "name": "Экономный",
        "desc": "Маленькие файлы, приемлемое качество",
        "target_pdf_mb": 30,
        "min_jpeg_quality": 65,
        "max_jpeg_quality": 78,
        "min_page_dimension": 800,
    },
    "medium": {
        "name": "Стандарт",
        "desc": "Баланс размера и качества",
        "target_pdf_mb": 80,
        "min_jpeg_quality": 78,
        "max_jpeg_quality": 92,
        "min_page_dimension": 1200,
    },
    "high": {
        "name": "Высокое",
        "desc": "Большие файлы, отличное качество",
        "target_pdf_mb": 200,
        "min_jpeg_quality": 88,
        "max_jpeg_quality": 96,
        "min_page_dimension": 1600,
    },
    "max": {
        "name": "Максимум",
        "desc": "Без сжатия, оригинальное разрешение",
        "target_pdf_mb": 9999,
        "min_jpeg_quality": 95,
        "max_jpeg_quality": 98,
        "min_page_dimension": 2400,
    },
}


def ensure_dirs():
    """Создаёт все необходимые директории."""
    for d in [DATA_DIR, OUTPUT_DIR, ASSETS_DIR]:
        os.makedirs(d, exist_ok=True)


def apply_preset(preset_key: str) -> bool:
    """Применяет пресет качества."""
    global TARGET_PDF_MB, MIN_JPEG_QUALITY, MAX_JPEG_QUALITY, MIN_PAGE_DIMENSION

    preset = QUALITY_PRESETS.get(preset_key)
    if not preset:
        return False

    TARGET_PDF_MB = preset["target_pdf_mb"]
    MIN_JPEG_QUALITY = preset["min_jpeg_quality"]
    MAX_JPEG_QUALITY = preset["max_jpeg_quality"]
    MIN_PAGE_DIMENSION = preset["min_page_dimension"]
    return True


def apply_custom_settings(
    target_mb: int,
    min_quality: int,
    max_quality: int,
    min_dimension: int,
) -> None:
    """Применяет пользовательские настройки качества."""
    global TARGET_PDF_MB, MIN_JPEG_QUALITY, MAX_JPEG_QUALITY, MIN_PAGE_DIMENSION

    TARGET_PDF_MB = max(5, min(9999, target_mb))
    MIN_JPEG_QUALITY = max(30, min(98, min_quality))
    MAX_JPEG_QUALITY = max(MIN_JPEG_QUALITY, min(99, max_quality))
    MIN_PAGE_DIMENSION = max(400, min(2400, min_dimension))


def get_current_settings_str() -> str:
    """Строка с текущими настройками для вывода."""
    return (
        f"PDF ~{TARGET_PDF_MB} МБ | "
        f"JPEG {MIN_JPEG_QUALITY}-{MAX_JPEG_QUALITY}% | "
        f"Мин. {MIN_PAGE_DIMENSION}px"
    )