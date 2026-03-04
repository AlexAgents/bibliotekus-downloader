#!/usr/bin/env python3
"""
Генерирует SHA-256 хеши для файлов в dist/.
Результат в dist/checksums.txt и в консоль.
"""

import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha256_file(filepath: str) -> str:
    """Считает SHA-256 хеш файла."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist_dir = os.path.join(project_root, "dist")

    if not os.path.exists(dist_dir):
        print("❌ Папка dist/ не найдена. Сначала соберите EXE.")
        return

    files = sorted([
        f for f in os.listdir(dist_dir)
        if os.path.isfile(os.path.join(dist_dir, f))
        and not f.endswith(".txt")
    ])

    if not files:
        print("❌ В dist/ нет файлов.")
        return

    print(f"\n{'═' * 60}")
    print(f"  🔐 SHA-256 Checksums")
    print(f"{'═' * 60}\n")

    lines = []
    for filename in files:
        filepath = os.path.join(dist_dir, filename)
        file_hash = sha256_file(filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)

        line = f"{file_hash}  {filename}"
        lines.append(line)

        print(f"  {filename}")
        print(f"  {file_hash}")
        print(f"  {size_mb:.1f} MB\n")

    # Сохраняем
    checksum_path = os.path.join(dist_dir, "checksums.txt")
    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"{'─' * 60}")
    print(f"  ✅ Сохранено: {checksum_path}")
    print(f"{'═' * 60}")

    # для GitHub
    print(f"\n📋 Для GitHub:\n")
    print(f"## SHA-256 Checksums\n")
    print(f"```")
    for line in lines:
        print(line)
    print(f"```")
    print(f"\nВерификация (PowerShell):")
    print(f"```powershell")
    for filename in files:
        print(f'Get-FileHash "{filename}" -Algorithm SHA256 | Format-List')
    print(f"```")
    print(f"\nВерификация (Linux/macOS):")
    print(f"```bash")
    print(f"sha256sum -c checksums.txt")
    print(f"```")


if __name__ == "__main__":
    main()