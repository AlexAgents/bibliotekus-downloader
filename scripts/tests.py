#!/usr/bin/env python3
"""
Тесты для проверки работоспособности проекта.

Запуск:
    python scripts/tests.py         — все тесты
    python scripts/tests.py -v      — подробно
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from io import BytesIO, StringIO

# Корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def suppress_stdout(func):
    """Декоратор — подавляет print() внутри теста."""
    def wrapper(*args, **kwargs):
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            return func(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
    return wrapper


# ═══════════════════════════════════════════════
# Тесты утилит
# ═══════════════════════════════════════════════

class TestUtils(unittest.TestCase):

    def test_sanitize_removes_forbidden(self):
        from utils import sanitize_filename
        result = sanitize_filename('Book: "Title" <test>')
        for ch in '"<>:':
            self.assertNotIn(ch, result)

    def test_sanitize_collapses_spaces(self):
        from utils import sanitize_filename
        self.assertEqual(sanitize_filename("too   many    spaces"), "too many spaces")

    def test_sanitize_truncates(self):
        from utils import sanitize_filename
        self.assertLessEqual(len(sanitize_filename("A" * 300)), 200)

    def test_pdf_filename_has_slug(self):
        from utils import get_pdf_filename
        book = {"title": "Test Book", "slug": "test-123"}
        result = get_pdf_filename(book)
        self.assertIn("[test-123]", result)
        self.assertTrue(result.endswith(".pdf"))

    def test_pdf_filename_uniqueness(self):
        from utils import get_pdf_filename
        b1 = {"title": "Same", "slug": "slug-001"}
        b2 = {"title": "Same", "slug": "slug-002"}
        self.assertNotEqual(get_pdf_filename(b1), get_pdf_filename(b2))

    def test_old_filename(self):
        from utils import get_old_filename
        book = {"title": "My Book", "slug": "x"}
        result = get_old_filename(book)
        self.assertEqual(result, "My Book.pdf")
        self.assertNotIn("[", result)

    def test_is_downloaded_false(self):
        from utils import is_downloaded
        self.assertFalse(is_downloaded({"title": "No", "slug": "nonexistent-xyz-999"}))

    def test_format_size_bytes(self):
        from utils import format_size
        self.assertIn("B", format_size(500))

    def test_format_size_kb(self):
        from utils import format_size
        self.assertIn("КБ", format_size(2048))

    def test_format_size_mb(self):
        from utils import format_size
        self.assertIn("МБ", format_size(5 * 1024 * 1024))

    def test_format_size_gb(self):
        from utils import format_size
        self.assertIn("ГБ", format_size(2 * 1024 ** 3))

    def test_make_ranges_consecutive(self):
        from utils import make_ranges
        self.assertEqual(make_ranges([1, 2, 3, 5, 7, 8, 9]), "1-3,5,7-9")

    def test_make_ranges_single(self):
        from utils import make_ranges
        self.assertEqual(make_ranges([1]), "1")

    def test_make_ranges_empty(self):
        from utils import make_ranges
        self.assertEqual(make_ranges([]), "")

    def test_make_ranges_gaps(self):
        from utils import make_ranges
        self.assertEqual(make_ranges([3, 5]), "3,5")

    def test_make_ranges_dedup(self):
        from utils import make_ranges
        self.assertEqual(make_ranges([1, 1, 2, 2, 3]), "1-3")


# ═══════════════════════════════════════════════
# Тесты конфигурации
# ═══════════════════════════════════════════════

class TestConfig(unittest.TestCase):

    def setUp(self):
        import config
        self._orig = {
            "TARGET_PDF_MB": config.TARGET_PDF_MB,
            "MIN_JPEG_QUALITY": config.MIN_JPEG_QUALITY,
            "MAX_JPEG_QUALITY": config.MAX_JPEG_QUALITY,
            "MIN_PAGE_DIMENSION": config.MIN_PAGE_DIMENSION,
        }

    def tearDown(self):
        import config
        for k, v in self._orig.items():
            setattr(config, k, v)

    def test_apply_preset_medium(self):
        from config import apply_preset, QUALITY_PRESETS
        import config
        self.assertTrue(apply_preset("medium"))
        self.assertEqual(config.TARGET_PDF_MB, QUALITY_PRESETS["medium"]["target_pdf_mb"])

    def test_apply_preset_invalid(self):
        from config import apply_preset
        self.assertFalse(apply_preset("nonexistent"))

    def test_apply_all_presets(self):
        from config import apply_preset, QUALITY_PRESETS
        for key in QUALITY_PRESETS:
            self.assertTrue(apply_preset(key), f"Пресет '{key}' не применился")

    def test_custom_settings(self):
        from config import apply_custom_settings
        import config
        apply_custom_settings(50, 70, 90, 1000)
        self.assertEqual(config.TARGET_PDF_MB, 50)
        self.assertEqual(config.MIN_JPEG_QUALITY, 70)
        self.assertEqual(config.MAX_JPEG_QUALITY, 90)
        self.assertEqual(config.MIN_PAGE_DIMENSION, 1000)

    def test_custom_clamps_min(self):
        from config import apply_custom_settings
        import config
        apply_custom_settings(1, 10, 20, 100)
        self.assertGreaterEqual(config.TARGET_PDF_MB, 5)
        self.assertGreaterEqual(config.MIN_JPEG_QUALITY, 30)
        self.assertGreaterEqual(config.MIN_PAGE_DIMENSION, 400)

    def test_custom_clamps_max(self):
        from config import apply_custom_settings
        import config
        apply_custom_settings(99999, 99, 100, 9999)
        self.assertLessEqual(config.TARGET_PDF_MB, 9999)
        self.assertLessEqual(config.MAX_JPEG_QUALITY, 99)
        self.assertLessEqual(config.MIN_PAGE_DIMENSION, 2400)

    def test_settings_string(self):
        from config import get_current_settings_str
        s = get_current_settings_str()
        self.assertIn("PDF", s)
        self.assertIn("JPEG", s)
        self.assertIn("Мін" if False else "Мін" if False else "Мин", s)

    @suppress_stdout
    def test_ensure_dirs(self):
        from config import ensure_dirs, DATA_DIR, OUTPUT_DIR, ASSETS_DIR
        ensure_dirs()
        self.assertTrue(os.path.isdir(DATA_DIR))
        self.assertTrue(os.path.isdir(OUTPUT_DIR))
        self.assertTrue(os.path.isdir(ASSETS_DIR))

    def test_project_root_not_temp(self):
        """PROJECT_ROOT не должен указывать на временную папку."""
        from config import PROJECT_ROOT
        if not getattr(sys, "frozen", False):
            self.assertNotIn("_mei", PROJECT_ROOT.lower())

    def test_version_exists(self):
        from config import VERSION
        self.assertIsInstance(VERSION, str)
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")


# ═══════════════════════════════════════════════
# Тесты оптимизатора
# ═══════════════════════════════════════════════

class TestImageOptimizer(unittest.TestCase):

    def test_no_compression_needed(self):
        from image_optimizer import calculate_optimal_settings
        q, r = calculate_optimal_settings(10, 1000, 800, 600)
        self.assertGreater(q, 85)
        self.assertEqual(r, 0)

    def test_heavy_compression(self):
        from image_optimizer import calculate_optimal_settings
        q, r = calculate_optimal_settings(200, 500_000, 3500, 2500)
        self.assertLessEqual(q, 85)
        self.assertGreater(r, 0)

    def test_zero_pages(self):
        from image_optimizer import calculate_optimal_settings
        q, r = calculate_optimal_settings(0, 0, 0, 0)
        self.assertGreater(q, 0)
        self.assertEqual(r, 0)

    def test_optimize_creates_jpeg(self):
        from image_optimizer import smart_optimize_image
        from PIL import Image
        img = Image.new("RGB", (100, 100), "red")
        buf = BytesIO()
        img.save(buf, format="PNG")
        result, w, h = smart_optimize_image(buf.getvalue(), 85, 0)
        self.assertGreater(len(result), 0)
        self.assertEqual(w, 100)
        self.assertEqual(h, 100)

    def test_optimize_rgba(self):
        from image_optimizer import smart_optimize_image
        from PIL import Image
        img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
        buf = BytesIO()
        img.save(buf, format="PNG")
        result, w, h = smart_optimize_image(buf.getvalue(), 85, 0)
        self.assertGreater(len(result), 0)
        self.assertEqual(w, 200)

    def test_optimize_resizes(self):
        from image_optimizer import smart_optimize_image
        from PIL import Image
        img = Image.new("RGB", (3000, 2000), "blue")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=95)
        result, w, h = smart_optimize_image(buf.getvalue(), 80, 1500)
        self.assertEqual(w, 3000)
        self.assertEqual(h, 2000)
        result_img = Image.open(BytesIO(result))
        self.assertLessEqual(max(result_img.size), 1500)
        result_img.close()

    def test_optimize_small_no_resize(self):
        """Маленькие изображения не должны ресайзиться."""
        from image_optimizer import smart_optimize_image
        from PIL import Image
        img = Image.new("RGB", (500, 400), "green")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        result, w, h = smart_optimize_image(buf.getvalue(), 80, 1500)
        self.assertEqual(w, 500)
        self.assertEqual(h, 400)


# ═══════════════════════════════════════════════
# Тесты PDF
# ═══════════════════════════════════════════════

class TestPdfBuilder(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _img(self, name, size=(100, 100)):
        from PIL import Image
        path = os.path.join(self.temp_dir, name)
        img = Image.new("RGB", size, "green")
        img.save(path, format="JPEG")
        img.close()
        return path

    def test_creates_file(self):
        from pdf_builder import build_pdf_from_files
        pages = [self._img(f"p{i}.jpg") for i in range(3)]
        out = os.path.join(self.temp_dir, "test.pdf")
        self.assertTrue(build_pdf_from_files(pages, out))
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 100)

    @suppress_stdout
    def test_empty_list(self):
        from pdf_builder import build_pdf_from_files
        out = os.path.join(self.temp_dir, "empty.pdf")
        self.assertFalse(build_pdf_from_files([], out))

    @suppress_stdout
    def test_nonexistent(self):
        from pdf_builder import build_pdf_from_files
        out = os.path.join(self.temp_dir, "fail.pdf")
        self.assertFalse(build_pdf_from_files(["/no/such/file.jpg"], out))

    def test_with_none(self):
        from pdf_builder import build_pdf_from_files
        pages = [self._img("p1.jpg"), None, self._img("p3.jpg")]
        out = os.path.join(self.temp_dir, "partial.pdf")
        self.assertTrue(build_pdf_from_files(pages, out))

    def test_various_sizes(self):
        from pdf_builder import build_pdf_from_files
        pages = [
            self._img("small.jpg", (100, 100)),
            self._img("wide.jpg", (800, 200)),
            self._img("tall.jpg", (200, 800)),
        ]
        out = os.path.join(self.temp_dir, "mixed.pdf")
        self.assertTrue(build_pdf_from_files(pages, out))


# ═══════════════════════════════════════════════
# Тесты CLI
# ═══════════════════════════════════════════════

class TestCli(unittest.TestCase):

    def test_all_y(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("y", 5), [1, 2, 3, 4, 5])

    def test_all_empty(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("", 5), [1, 2, 3, 4, 5])

    def test_none_n(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("n", 5), [])

    def test_quit_q(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("q", 5), [])

    def test_quit_exit(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("exit", 5), [])

    def test_single(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("3", 10), [3])

    def test_list(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("1,3,5", 10), [1, 3, 5])

    def test_range(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("3-6", 10), [3, 4, 5, 6])

    def test_open_range(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("8-", 10), [8, 9, 10])

    def test_combo(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("1-3,7,9-10", 10), [1, 2, 3, 7, 9, 10])

    def test_out_of_range(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("0,5,100", 10), [5])

    def test_invalid_text(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("abc", 10), [])

    def test_spaces(self):
        from cli import parse_selection
        self.assertEqual(parse_selection(" 1 , 3 , 5 ", 10), [1, 3, 5])

    def test_single_first(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("1", 100), [1])

    def test_single_last(self):
        from cli import parse_selection
        self.assertEqual(parse_selection("100", 100), [100])


# ═══════════════════════════════════════════════
# Тесты сети (мокаем — без реальных запросов)
# ═══════════════════════════════════════════════

class TestNetwork(unittest.TestCase):

    def test_session_exists(self):
        from network import session
        self.assertIsNotNone(session)

    def test_session_has_user_agent(self):
        from network import session
        self.assertIn("User-Agent", session.headers)

    def test_session_has_referer(self):
        from network import session
        self.assertIn("Referer", session.headers)

    @patch("network.session")
    def test_safe_get_error(self, mock_session):
        from network import safe_get
        import requests
        mock_session.get.side_effect = requests.ConnectionError("fail")
        self.assertIsNone(safe_get("http://example.com/bad"))

    @patch("network.session")
    def test_safe_get_success(self, mock_session):
        from network import safe_get
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_resp
        self.assertIsNotNone(safe_get("http://example.com/ok"))

    @patch("network.session")
    def test_safe_head_error(self, mock_session):
        from network import safe_head
        import requests
        mock_session.head.side_effect = requests.ConnectionError("fail")
        self.assertIsNone(safe_head("http://example.com/bad"))

    @patch("network.session")
    def test_safe_head_success(self, mock_session):
        from network import safe_head
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_session.head.return_value = mock_resp
        self.assertIsNotNone(safe_head("http://example.com/ok"))

    @patch("network.session")
    def test_safe_get_timeout(self, mock_session):
        from network import safe_get
        import requests
        mock_session.get.side_effect = requests.Timeout("timeout")
        self.assertIsNone(safe_get("http://example.com/slow"))


# ═══════════════════════════════════════════════
# Тесты скрапера (моки — без реальных запросов)
# ═══════════════════════════════════════════════

class TestScraper(unittest.TestCase):

    MOCK_MAIN = """
    <html><body>
        <div class="books__item">
            <a class="books__link" href="/books/test-book/">
            <h2 class="books__title">Test Book</h2></a>
        </div>
        <div class="books__item">
            <a class="books__link" href="/books/another/">
            <h2 class="books__title">Another</h2></a>
        </div>
    </body></html>
    """

    MOCK_BOOK = """
    <html><body>
        <div class="book__page">
            <img class="book__thumb" src="/img/books/test/001-400.jpg">
            <span class="page-number">1</span>
            <a class="book__link" href="/books/test/page/1/">link</a>
        </div>
        <div class="book__page">
            <img class="book__thumb" src="/img/books/test/002-400.jpg">
            <span class="page-number">2</span>
        </div>
    </body></html>
    """

    @suppress_stdout
    @patch("scraper.session")
    def test_get_book_links(self, mock_session):
        from scraper import get_book_links
        resp = MagicMock()
        resp.text = self.MOCK_MAIN
        resp.raise_for_status = MagicMock()
        mock_session.get.return_value = resp

        books = get_book_links()
        self.assertEqual(len(books), 2)
        self.assertEqual(books[0]["title"], "Test Book")
        self.assertEqual(books[0]["slug"], "test-book")
        self.assertEqual(books[1]["slug"], "another")

    @patch("scraper.session")
    def test_get_pages(self, mock_session):
        from scraper import get_page_count_and_images
        resp = MagicMock()
        resp.text = self.MOCK_BOOK
        resp.raise_for_status = MagicMock()
        mock_session.get.return_value = resp

        pages = get_page_count_and_images("http://test.com/book")
        self.assertEqual(len(pages), 2)
        self.assertIn("001-400.jpg", pages[0]["thumb_src"])
        self.assertEqual(pages[0]["page_num"], 1)

    @suppress_stdout
    @patch("scraper.session")
    def test_empty_page(self, mock_session):
        from scraper import get_book_links
        resp = MagicMock()
        resp.text = "<html><body></body></html>"
        resp.raise_for_status = MagicMock()
        mock_session.get.return_value = resp
        self.assertEqual(len(get_book_links()), 0)

    @patch("scraper.session")
    def test_book_has_all_fields(self, mock_session):
        from scraper import get_book_links
        resp = MagicMock()
        resp.text = self.MOCK_MAIN
        resp.raise_for_status = MagicMock()
        mock_session.get.return_value = resp

        books = get_book_links()
        for book in books:
            self.assertIn("url", book)
            self.assertIn("title", book)
            self.assertIn("slug", book)
            self.assertIn("href", book)


# ═══════════════════════════════════════════════
# Интеграционный тест
# ═══════════════════════════════════════════════

class TestIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_pipeline(self):
        """Полный цикл: raw → optimize → PDF."""
        from PIL import Image
        from image_optimizer import optimize_and_save_page
        from pdf_builder import build_pdf_from_files

        raw = {}
        for i in range(3):
            img = Image.new("RGB", (800, 600), color=(i * 80, 100, 200))
            path = os.path.join(self.temp_dir, f"page_{i:04d}.raw")
            img.save(path, format="PNG")
            img.close()
            raw[i] = path

        opt = {}
        for i, path in raw.items():
            result = optimize_and_save_page((i, path, 85, 0, self.temp_dir))
            idx, opt_path, orig, optim, w, h = result
            self.assertIsNotNone(opt_path, f"Страница {i} не оптимизировалась")
            self.assertGreater(optim, 0)
            opt[i] = opt_path

        out = os.path.join(self.temp_dir, "result.pdf")
        self.assertTrue(build_pdf_from_files([opt[i] for i in sorted(opt)], out))
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 100)


# ═══════════════════════════════════════════════
# Тесты downloader (флаги)
# ═══════════════════════════════════════════════

class TestDownloaderFlags(unittest.TestCase):

    def setUp(self):
        import downloader
        self._orig = downloader._shutdown_requested
        downloader._shutdown_requested = False

    def tearDown(self):
        import downloader
        downloader._shutdown_requested = self._orig

    @suppress_stdout
    def test_shutdown_initially_false(self):
        import downloader
        self.assertFalse(downloader.is_shutdown_requested())

    @suppress_stdout
    def test_shutdown_after_request(self):
        import downloader
        downloader.request_shutdown()
        self.assertTrue(downloader.is_shutdown_requested())

    @suppress_stdout
    def test_shutdown_reset(self):
        import downloader
        downloader.request_shutdown()
        self.assertTrue(downloader.is_shutdown_requested())
        downloader._shutdown_requested = False
        self.assertFalse(downloader.is_shutdown_requested())


# ═══════════════════════════════════════════════
# Запуск
# ═══════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("🧪 Bibliotekus Downloader — Тесты")
    print("=" * 60)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestUtils,
        TestConfig,
        TestImageOptimizer,
        TestPdfBuilder,
        TestCli,
        TestNetwork,
        TestScraper,
        TestIntegration,
        TestDownloaderFlags,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    verbosity = 2 if "-v" in sys.argv else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    print(f"\n{'=' * 60}")
    total = result.testsRun
    fails = len(result.failures)
    errs = len(result.errors)
    passed = total - fails - errs

    print(f"📊 Всего: {total} | ✅ {passed} | ❌ {fails} | 💀 {errs}")

    if result.wasSuccessful():
        print("🎉 Все тесты пройдены!")
    else:
        if result.failures:
            print(f"\n❌ Упавшие тесты:")
            for test, _ in result.failures:
                print(f"   • {test}")
        if result.errors:
            print(f"\n💀 Ошибки:")
            for test, _ in result.errors:
                print(f"   • {test}")

    print("=" * 60)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())