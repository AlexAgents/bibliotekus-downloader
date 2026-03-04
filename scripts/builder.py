#!/usr/bin/env python3
"""
builder.py — Сборка EXE-файла bibliotekus.exe.

Запуск: python scripts/builder.py

Требования: pip install pyinstaller pillow
"""

import sys
import os
import subprocess
import struct
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    PROJECT_ROOT, ASSETS_DIR,
    ICON_MAIN, ENTRY_POINT,
    ensure_dirs,
)


# ═══════════════════════════════════════════════
# Генерация иконки
# ═══════════════════════════════════════════════

def generate_icon():
    """Генерирует .ico если его нет в assets/."""
    ensure_dirs()

    if os.path.exists(ICON_MAIN):
        print("  ✅ Иконка уже существует")
        return True

    try:
        from PIL import Image, ImageDraw  # type: ignore[import-untyped]
        return _generate_with_pillow()
    except ImportError:
        print("  ⚠ Pillow не установлен, создаю минимальную иконку")
        return _generate_minimal_ico()


def _generate_with_pillow() -> bool:
    """Генерирует иконку через Pillow."""
    from PIL import Image, ImageDraw  # type: ignore[import-untyped]

    color = (52, 152, 219)
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        margin = max(1, size // 16)
        draw.rounded_rectangle(
            [margin, margin, size - margin - 1, size - margin - 1],
            radius=max(2, size // 6),
            fill=color + (255,),
        )

        try:
            draw.text(
                (size // 2, size // 2),
                "Б",
                fill=(255, 255, 255, 255),
                anchor="mm",
            )
        except Exception:
            inner = size // 4
            draw.ellipse(
                [inner, inner, size - inner, size - inner],
                fill=(255, 255, 255, 200),
            )

        images.append(img)

    images[0].save(
        ICON_MAIN,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"  ✅ Создана иконка: {os.path.basename(ICON_MAIN)}")
    return True


def _generate_minimal_ico() -> bool:
    """Генерирует минимальный .ico БЕЗ Pillow (32x32)."""
    r, g, b = 52, 152, 219
    size = 32

    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            border = 3
            if border <= x < size - border and border <= y < size - border:
                pixels.extend([b, g, r, 255])
            else:
                pixels.extend([0, 0, 0, 0])

    mask_row_bytes = (size + 31) // 32 * 4
    and_mask = bytearray(mask_row_bytes * size)

    bmp_header = struct.pack(
        "<IiiHHIIiiII",
        40, size, size * 2, 1, 32, 0,
        len(pixels) + len(and_mask),
        0, 0, 0, 0,
    )

    image_data = bmp_header + bytes(pixels) + bytes(and_mask)
    ico_header = struct.pack("<HHH", 0, 1, 1)
    data_offset = 6 + 16
    ico_entry = struct.pack(
        "<BBBBHHII",
        size, size, 0, 0, 1, 32,
        len(image_data), data_offset,
    )

    with open(ICON_MAIN, "wb") as f:
        f.write(ico_header)
        f.write(ico_entry)
        f.write(image_data)

    print(f"  ✅ Иконка (минимальная): {os.path.basename(ICON_MAIN)}")
    return True


# ═══════════════════════════════════════════════
# Проверки
# ═══════════════════════════════════════════════

def check_pyinstaller() -> bool:
    """Проверяет наличие PyInstaller."""
    try:
        import PyInstaller
        print(f"  ✅ PyInstaller {PyInstaller.__version__}")
        return True
    except ImportError:
        print("  ❌ PyInstaller не установлен!")
        return False


def install_pyinstaller() -> bool:
    """Устанавливает PyInstaller."""
    print("\n  Установка PyInstaller...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True, capture_output=True, text=True,
        )
        print("  ✅ PyInstaller установлен")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Ошибка установки: {e}")
        return False


def check_entry_point() -> bool:
    """Проверяет что точка входа существует."""
    if os.path.exists(ENTRY_POINT):
        print(f"  ✅ Точка входа: {os.path.basename(ENTRY_POINT)}")
        return True
    else:
        print(f"  ❌ Не найден ни __main__.py, ни main.py!")
        return False


# ═══════════════════════════════════════════════
# Сборка EXE
# ═══════════════════════════════════════════════

def build_exe() -> bool:
    """Собирает bibliotekus.exe."""
    script_path = ENTRY_POINT
    exe_name = "bibliotekus"

    if not os.path.exists(script_path):
        print(f"  ❌ Скрипт не найден: {script_path}")
        return False

    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    build_dir = os.path.join(PROJECT_ROOT, "build")

    print(f"\n{'═' * 60}")
    print(f"  🔨 Сборка: {exe_name}.exe")
    print(f"     Скрипт: {os.path.relpath(script_path, PROJECT_ROOT)}")
    if os.path.exists(ICON_MAIN):
        print(f"     Иконка: {os.path.relpath(ICON_MAIN, PROJECT_ROOT)}")
    print(f"{'═' * 60}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconfirm",
        "--clean",
        "--console",
        f"--name={exe_name}",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={build_dir}",
    ]

    if os.path.exists(ICON_MAIN):
        cmd.append(f"--icon={ICON_MAIN}")

    # Модули проекта
    for module_name in (
        "config.py", "logger.py", "network.py", "utils.py",
        "scraper.py", "downloader.py", "image_optimizer.py",
        "pdf_builder.py", "cli.py",
    ):
        module_path = os.path.join(PROJECT_ROOT, module_name)
        if os.path.exists(module_path):
            cmd.append(f"--add-data={module_path}{os.pathsep}.")

    # Hidden imports
    hidden = [
        "config", "logger", "network", "utils",
        "scraper", "downloader", "image_optimizer",
        "pdf_builder", "cli",
        "requests", "bs4", "PIL",
        "fpdf", "reportlab", "reportlab.pdfgen",
        "urllib3", "charset_normalizer", "certifi", "idna",
    ]
    for hi in hidden:
        cmd.append(f"--hidden-import={hi}")

    cmd.append(script_path)

    print(f"\n  ⏳ Сборка... (1-3 минуты)")

    try:
        result = subprocess.run(
            cmd, cwd=PROJECT_ROOT,
            capture_output=True, text=True, timeout=600,
        )

        if result.returncode == 0:
            exe_suffix = ".exe" if sys.platform == "win32" else ""
            exe_path = os.path.join(dist_dir, f"{exe_name}{exe_suffix}")

            if os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"\n  ✅ Готово: {exe_path}")
                print(f"     Размер: {size_mb:.1f} MB")
                print(f"\n  📂 Книги будут сохраняться в:")
                print(f"     <папка с exe>/data/books_pdf/")
                return True
            else:
                print(f"\n  ⚠ PyInstaller завершился, но EXE не найден")
                return False
        else:
            print(f"\n  ❌ Ошибка сборки (код {result.returncode})!")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[-20:]:
                    print(f"    {line}")
            return False

    except subprocess.TimeoutExpired:
        print(f"\n  ❌ Таймаут (>10 мин)")
        return False
    except Exception as e:
        print(f"\n  ❌ {e}")
        return False


# ═══════════════════════════════════════════════
# Очистка
# ═══════════════════════════════════════════════

def clean_build():
    """Удаляет временные файлы сборки."""
    cleaned = False

    build_dir = os.path.join(PROJECT_ROOT, "build")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir, ignore_errors=True)
        print("  🗑 Удалена папка build/")
        cleaned = True

    for f in os.listdir(PROJECT_ROOT):
        if f.endswith(".spec"):
            os.remove(os.path.join(PROJECT_ROOT, f))
            print(f"  🗑 Удалён {f}")
            cleaned = True

    for root, dirs, _ in os.walk(PROJECT_ROOT):
        for d in dirs:
            if d == "__pycache__":
                path = os.path.join(root, d)
                shutil.rmtree(path, ignore_errors=True)
                print(f"  🗑 Удалён {os.path.relpath(path, PROJECT_ROOT)}")
                cleaned = True

    if not cleaned:
        print("  ✅ Нечего удалять")


def clean_dist():
    """Удаляет собранные EXE."""
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir, ignore_errors=True)
        print("  🗑 Удалена папка dist/")
    else:
        print("  ✅ Папка dist/ не существует")


# ═══════════════════════════════════════════════
# Статус
# ═══════════════════════════════════════════════

def show_status() -> str:
    """Показывает статус EXE."""
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    exe_suffix = ".exe" if sys.platform == "win32" else ""
    exe_path = os.path.join(dist_dir, f"bibliotekus{exe_suffix}")

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        from datetime import datetime
        mtime = os.path.getmtime(exe_path)
        dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        return f"✅ {size_mb:.1f} MB ({dt})"
    else:
        return "⬚ не собран"


# ═══════════════════════════════════════════════
# Интерактивное меню
# ═══════════════════════════════════════════════

def interactive_menu():
    """Главное меню builder."""
    print("\n  📁 Проверка файлов...")
    check_entry_point()
    generate_icon()

    while True:
        status = show_status()
        ico_status = "✅" if os.path.exists(ICON_MAIN) else "⬚"

        print(f"\n{'═' * 60}")
        print(f"  🔨 BUILDER — Сборка bibliotekus.exe")
        print(f"{'═' * 60}")
        print(f"  Точка входа: {os.path.basename(ENTRY_POINT)}")
        print(f"  Иконка: {ico_status}")
        print(f"{'─' * 60}")
        print(f"  {status:<35} 1. Собрать bibliotekus.exe")
        print(f"{'─' * 60}")
        print(f"  {'':35} 2. Перегенерировать иконку")
        print(f"  {'':35} 3. Очистить build/ (временные)")
        print(f"  {'':35} 4. Очистить dist/ (EXE)")
        print(f"  {'':35} 5. Очистить всё")
        print(f"  {'':35} q. Выход")
        print(f"{'─' * 60}")

        choice = input("\n  ▶ Выбор: ").strip().lower()

        if choice in ("q", "quit", "exit", "й"):
            break
        elif choice == "1":
            build_exe()
        elif choice == "2":
            if os.path.exists(ICON_MAIN):
                os.remove(ICON_MAIN)
            generate_icon()
        elif choice == "3":
            clean_build()
        elif choice == "4":
            clean_dist()
        elif choice == "5":
            clean_build()
            clean_dist()
        else:
            print("  ⚠ Неизвестная команда")

        input("\n  ⏎ Enter для продолжения...")

    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    print(f"\n  👋 Готово!")
    if os.path.exists(dist_dir) and os.listdir(dist_dir):
        print(f"     EXE: {dist_dir}")


def main():
    print("=" * 60)
    print("  🔨 BUILDER — Bibliotekus")
    print("=" * 60)

    ensure_dirs()

    if not check_pyinstaller():
        ans = input("\n  Установить PyInstaller? (y/n) [y]: ").strip().lower()
        if ans in ("y", "yes", "да", "д", ""):
            if not install_pyinstaller():
                return
        else:
            print("  ❌ PyInstaller необходим")
            return

    interactive_menu()


if __name__ == "__main__":
    main()