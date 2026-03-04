"""
Логирование: консоль + файл.
"""

import os
import sys
import logging
import threading

from config import LOG_FILE, LOG_LEVEL, DATA_DIR

_initialized = False
_lock = threading.Lock()


def setup_logging() -> logging.Logger:
    """Инициализирует логгер один раз."""
    global _initialized

    with _lock:
        if _initialized:
            return logging.getLogger("bibliotekus")

        logger = logging.getLogger("bibliotekus")
        logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
        logger.propagate = False

        # Консоль
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console)

        # Файл
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)-7s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            logger.addHandler(fh)
        except OSError:
            logger.warning(f"Не удалось создать лог-файл: {LOG_FILE}")

        _initialized = True
        return logger


def get_logger(name: str = "") -> logging.Logger:
    """Получить логгер."""
    setup_logging()
    if name:
        return logging.getLogger(f"bibliotekus.{name}")
    return logging.getLogger("bibliotekus")