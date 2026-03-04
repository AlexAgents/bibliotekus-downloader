#!/usr/bin/env python3
"""
Проверка и исправление библиотеки скачанных книг.
Запуск:  python -m scripts.verify
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OUTPUT_DIR, ensure_dirs
from utils import get_pdf_filename, get_old_filename, make_ranges, prompt_continue, exit_app
from scraper import get_book_links, get_expected_page_count
from logger import get_logger

log = get_logger("verify")

try:
    import fitz  # type: ignore[import-untyped]
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False
    print("⚠ PyMuPDF не установлен (pip install PyMuPDF)")
    print("  Проверка страниц PDF будет ограничена\n")


def scan_existing_files() -> list[dict]:
    if not os.path.exists(OUTPUT_DIR):
        return []
    files = []
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if not f.lower().endswith(".pdf"):
            continue
        path = os.path.join(OUTPUT_DIR, f)
        files.append({
            "filename": f,
            "path": path,
            "size_mb": os.path.getsize(path) / (1024 * 1024),
        })
    return files


def get_pdf_pages(pdf_path: str) -> int:
    if not HAS_FITZ:
        return -2
    try:
        doc = fitz.open(pdf_path)
        count = doc.page_count
        doc.close()
        return count
    except Exception:
        return -1


def match_files_to_books(books, files):
    matched = {}
    used = set()

    for i, book in enumerate(books):
        new_name = get_pdf_filename(book)
        for fi, f in enumerate(files):
            if f["filename"] == new_name and fi not in used:
                matched[i] = f
                used.add(fi)
                break

    old_counts = {}
    for book in books:
        old = get_old_filename(book)
        old_counts[old] = old_counts.get(old, 0) + 1

    for i, book in enumerate(books):
        if i in matched:
            continue
        old_name = get_old_filename(book)
        for fi, f in enumerate(files):
            if f["filename"] == old_name and fi not in used:
                matched[i] = f
                if old_counts[old_name] > 1:
                    matched[i]["ambiguous"] = True
                used.add(fi)
                break

    unmatched = [f for fi, f in enumerate(files) if fi not in used]
    missing = [i for i in range(len(books)) if i not in matched]
    return matched, unmatched, missing


def rename_matched_files(books, matched):
    renamed = already_ok = errors = 0
    for idx, finfo in matched.items():
        new_name = get_pdf_filename(books[idx])
        new_path = os.path.join(OUTPUT_DIR, new_name)
        if finfo["filename"] == new_name:
            already_ok += 1
            continue
        if os.path.exists(new_path):
            print(f"  ⚠ Конфликт: {new_name}")
            errors += 1
            continue
        try:
            os.rename(finfo["path"], new_path)
            print(f"  ✏️  {finfo['filename']}")
            print(f"   → {new_name}")
            finfo["filename"] = new_name
            finfo["path"] = new_path
            renamed += 1
        except Exception as e:
            print(f"  ⚠ {e}")
            errors += 1
    return renamed, already_ok, errors


def verify_books(books, matched):
    results = {"ok": [], "missing": [], "incomplete": [], "corrupted": [], "warnings": []}

    print(f"\n{'№':>4} {'Ст':>4} {'PDF':>5} {'Сайт':>5} {'Размер':>8}  Книга")
    print("-" * 70)

    for i, book in enumerate(books):
        num = i + 1
        short = book["title"][:40] + "..." if len(book["title"]) > 43 else book["title"]

        if i not in matched:
            print(f"{num:4d}  ❌  {'—':>5} {'—':>5} {'—':>8}  {short}")
            results["missing"].append(num)
            continue

        f = matched[i]
        size_mb = f["size_mb"]
        pdf_pages = get_pdf_pages(f["path"])

        if pdf_pages == -1:
            print(f"{num:4d}  💀  {'ERR':>5} {'—':>5} {size_mb:7.1f}M  {short}")
            results["corrupted"].append((num, "PDF повреждён"))
            continue

        expected = get_expected_page_count(book["url"])

        if pdf_pages == -2:
            if 0 < size_mb < 0.5:
                print(f"{num:4d}  ⚠️  {'?':>5} {expected if expected > 0 else '?':>5} {size_mb:7.1f}M  {short}")
                results["corrupted"].append((num, f"Маленький: {size_mb:.1f} МБ"))
            else:
                print(f"{num:4d}  ✅  {'?':>5} {expected if expected > 0 else '?':>5} {size_mb:7.1f}M  {short}")
                results["ok"].append(num)
            continue

        exp_str = str(expected) if expected > 0 else "?"

        if expected < 0:
            status = "⚠️"
            results["warnings"].append((num, "Не удалось проверить сайт"))
        elif pdf_pages < expected:
            status = "🔻"
            results["incomplete"].append((num, pdf_pages, expected, expected - pdf_pages, size_mb))
        elif pdf_pages > expected:
            status = "🔺"
            results["warnings"].append((num, f"Лишних {pdf_pages - expected} стр"))
            results["ok"].append(num)
        else:
            status = "✅"
            results["ok"].append(num)

        if size_mb < 1.0 and pdf_pages > 5 and num not in [c[0] for c in results["corrupted"]]:
            status = "⚠️"
            results["corrupted"].append((num, f"Подозрительный: {size_mb:.1f} МБ"))

        print(f"{num:4d}  {status:<4} {pdf_pages:>5} {exp_str:>5} {size_mb:7.1f}M  {short}")

    return results


def handle_redownload(books, redownload):
    ranges_str = make_ranges(redownload)

    to_delete = []
    for num in redownload:
        book = books[num - 1]
        for name in [get_pdf_filename(book), get_old_filename(book)]:
            path = os.path.join(OUTPUT_DIR, name)
            if os.path.exists(path):
                to_delete.append((num, path))
                break

    if to_delete:
        print(f"\n⚠ {len(to_delete)} проблемных файлов:\n")
        for num, path in to_delete:
            size = os.path.getsize(path) / (1024 * 1024)
            print(f"   {num:3d}. {os.path.basename(path)} ({size:.1f} МБ)")

        if input("\nУдалить? (y/n): ").strip().lower() == "y":
            for _, path in to_delete:
                try:
                    os.remove(path)
                    print(f"   🗑 {os.path.basename(path)}")
                except Exception as e:
                    print(f"   ⚠ {e}")

    print(f"\n📋 Для bibliotekus.exe введите:\n\n   {ranges_str}\n")


def run_verify():
    """Одна сессия проверки."""
    ensure_dirs()

    files = scan_existing_files()
    print(f"📂 PDF в папке: {len(files)}")
    if files:
        total = sum(f["size_mb"] for f in files)
        print(f"   Размер: {total:.1f} МБ ({total / 1024:.2f} ГБ)")

    books = get_book_links()
    if not books:
        print("Книги не найдены.")
        return

    # Дубликаты
    old_counts = {}
    for b in books:
        n = get_old_filename(b)
        old_counts[n] = old_counts.get(n, 0) + 1
    dups = {k: v for k, v in old_counts.items() if v > 1}
    if dups:
        print(f"\n⚠ Одинаковых названий: {sum(dups.values())} ({len(dups)} групп)")

    # Фаза 1
    print(f"\n{'=' * 70}\nФАЗА 1: Сопоставление\n{'=' * 70}")
    matched, unmatched, missing = match_files_to_books(books, files)
    print(f"\n  Сопоставлено: {len(matched)} | Нет файла: {len(missing)} | Лишние: {len(unmatched)}")

    ambiguous = [i for i, f in matched.items() if f.get("ambiguous")]
    if ambiguous:
        print(f"  Неоднозначные: {len(ambiguous)}")

    # Фаза 2
    if matched:
        to_rename = sum(1 for i, f in matched.items() if f["filename"] != get_pdf_filename(books[i]))
        print(f"\n{'=' * 70}\nФАЗА 2: Переименование\n{'=' * 70}")
        if to_rename == 0:
            print("\n  ✅ Все в новом формате")
        else:
            print(f"\n  Нужно: {to_rename}\n")
            r, ok, err = rename_matched_files(books, matched)
            print(f"\n  Переименовано: {r} | ОК: {ok} | Ошибки: {err}")

    # Фаза 3
    print(f"\n{'=' * 70}\nФАЗА 3: Проверка\n{'=' * 70}")
    files = scan_existing_files()
    matched, unmatched, missing = match_files_to_books(books, files)
    results = verify_books(books, matched)

    # Итоги
    print(f"\n{'=' * 70}\n📊 ИТОГИ\n{'=' * 70}")
    print(f"\n  ✅ ОК: {len(results['ok'])}")
    print(f"  ❌ Не скачаны: {len(results['missing'])}")
    print(f"  🔻 Неполные: {len(results['incomplete'])}")
    print(f"  💀 Повреждены: {len(results['corrupted'])}")
    print(f"  ⚠️  Предупреждения: {len(results['warnings'])}")

    for key, label in [
        ("missing", "❌ НЕ СКАЧАНЫ"),
        ("incomplete", "🔻 НЕПОЛНЫЕ"),
        ("corrupted", "💀 ПОВРЕЖДЕНЫ"),
        ("warnings", "⚠️  ПРЕДУПРЕЖДЕНИЯ"),
    ]:
        items = results[key]
        if not items:
            continue
        print(f"\n{label} ({len(items)}):")
        for item in items:
            if isinstance(item, int):
                print(f"   {item:3d}. {books[item - 1]['title']}")
            elif len(item) == 5:
                num, actual, expected, diff, size = item
                print(f"   {num:3d}. {books[num - 1]['title']}")
                print(f"        PDF: {actual} | Сайт: {expected} | -{diff} | {size:.1f} МБ")
            else:
                num, reason = item
                print(f"   {num:3d}. {books[num - 1]['title']}")
                print(f"        {reason}")

    # Перекачка
    redownload = set(results["missing"])
    for item in results["incomplete"]:
        redownload.add(item[0])
    for item in results["corrupted"]:
        redownload.add(item[0])

    if redownload:
        print(f"\n{'=' * 70}\n🔄 ПЕРЕКАЧАТЬ: {len(redownload)}\n{'=' * 70}")
        handle_redownload(books, sorted(redownload))
    else:
        count = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf")])
        print(f"\n🎉 Все {len(books)} книг на месте! ({count} файлов)")

    if unmatched:
        print(f"\n📎 Лишние файлы ({len(unmatched)}):")
        for f in unmatched:
            print(f"   {f['filename']} ({f['size_mb']:.1f} МБ)")

    print("=" * 70)


def main():
    """Главный цикл verify — с возможностью повторить."""
    while True:
        try:
            run_verify()
        except KeyboardInterrupt:
            print("\n\n⛔ Прервано.")
        except Exception as e:
            print(f"\n💀 Ошибка: {e}")
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