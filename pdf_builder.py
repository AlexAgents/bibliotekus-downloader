"""
Сборка PDF из JPEG-файлов. Два бэкенда: fpdf2, reportlab.
"""

import os
from PIL import Image
from logger import get_logger

log = get_logger("pdf")


def build_pdf_from_files(page_files: list[str | None], output_path: str) -> bool:
    """Собирает PDF. Пробует fpdf2, затем reportlab."""
    valid = [p for p in page_files if p and os.path.exists(p)]
    if not valid:
        log.warning("Нет файлов для PDF")
        return False

    if _build_fpdf(valid, output_path):
        return True
    return _build_reportlab(valid, output_path)


def _build_fpdf(files: list[str], output_path: str) -> bool:
    try:
        from fpdf import FPDF  # type: ignore[import-untyped]
    except ImportError:
        return False
    try:
        pdf = FPDF(unit="pt")
        pdf.set_auto_page_break(False)
        pdf.set_margin(0)
        for path in files:
            try:
                img = Image.open(path)
                w, h = img.size
                img.close()
                pdf.add_page(format=(w, h))
                pdf.image(path, x=0, y=0, w=w, h=h)
            except Exception as e:
                log.warning(f"Страница пропущена: {e}")
        pdf.output(output_path)
        return True
    except Exception as e:
        log.error(f"fpdf2: {e}")
        return False


def _build_reportlab(files: list[str], output_path: str) -> bool:
    try:
        from reportlab.pdfgen import canvas as rl_canvas  # type: ignore[import-untyped]
    except ImportError:
        log.error("Не установлен ни fpdf2, ни reportlab!")
        return False
    try:
        c = rl_canvas.Canvas(output_path)
        for path in files:
            try:
                img = Image.open(path)
                w, h = img.size
                img.close()
                c.setPageSize((w, h))
                c.drawImage(path, 0, 0, width=w, height=h)
                c.showPage()
            except Exception as e:
                log.warning(f"Страница пропущена: {e}")
        c.save()
        return True
    except Exception as e:
        log.error(f"reportlab: {e}")
        return False