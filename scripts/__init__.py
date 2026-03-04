"""
Вспомогательные скрипты Bibliotekus Downloader.

Модули
------
verify : Проверка и исправление библиотеки скачанных книг.
    Запуск: python -m scripts.verify

builder : Сборка bibliotekus.exe через PyInstaller.
    Запуск: python scripts/builder.py

checksum : Генерация SHA-256 хешей для файлов в dist/.
    Запуск: python scripts/checksum.py

tests : Тесты проекта (50+).
    Запуск: python scripts/tests.py [-v]

Полный цикл релиза
------------------
    python scripts/tests.py            # прогнать тесты
    python scripts/builder.py          # собрать EXE
    python scripts/checksum.py         # посчитать хеши
"""

__all__ = ["verify", "builder", "checksum", "tests"]