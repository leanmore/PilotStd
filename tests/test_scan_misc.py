# tests/test_scan_misc.py — scan/download/platform/cli/organizer 边界补测

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

_CI = os.environ.get("CI", "").lower() in ("true", "1")


class TestScannerModule(unittest.TestCase):
    def test_import_scanner(self):
        from pilotstd.scan.scanner import FileScanner
        self.assertTrue(hasattr(FileScanner, '__init__'))

    def test_import_watcher(self):
        from pilotstd.scan.watcher import FileWatcher
        self.assertTrue(hasattr(FileWatcher, '__init__'))

    def test_lang_detect_chinese(self):
        from pilotstd.scan.lang_detect import detect_language
        result = detect_language("GB/T 1.1-2020 标准化工作导则.pdf")
        self.assertIsInstance(result, str)

    def test_lang_detect_english(self):
        from pilotstd.scan.lang_detect import detect_language
        result = detect_language("ISO 9001 Quality Management.pdf")
        self.assertIsInstance(result, str)

    def test_parser_constants(self):
        from pilotstd.scan.parser._constants import FOREIGN_CODE_SET, ISO_IEC_SET
        self.assertIsInstance(FOREIGN_CODE_SET, (set, frozenset))
        # ISO is in ISO_IEC_SET, not FOREIGN_CODE_SET
        self.assertIn("ISO", ISO_IEC_SET)


class TestDownloadModule(unittest.TestCase):
    def test_import_engine(self):
        from pilotstd.download.engine import DownloadEngine
        self.assertTrue(hasattr(DownloadEngine, '__init__'))

    def test_import_models(self):
        from pilotstd.download.models import DownloadTask
        self.assertTrue(hasattr(DownloadTask, '__init__'))

    def test_openstd_adapter(self):
        from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
        self.assertTrue(hasattr(OpenstdDownloadAdapter, 'site_name'))


class TestPlatformModule(unittest.TestCase):
    @unittest.skipIf(_CI, "CI 环境无 PyQt6 显示支持")
    def test_notify_service(self):
        from pilotstd.platform.notify import NotifyService
        self.assertTrue(hasattr(NotifyService, '__init__'))

    def test_updater_functions(self):
        from pilotstd.platform.updater import check_latest_version, is_newer_version
        self.assertTrue(callable(check_latest_version))
        self.assertTrue(callable(is_newer_version))

    def test_is_newer_version(self):
        from pilotstd.platform.updater import is_newer_version
        self.assertTrue(is_newer_version("2.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("1.0.0", "2.0.0"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))

    def test_version_comparison(self):
        from pilotstd.platform.updater import is_newer_version
        self.assertTrue(is_newer_version("1.0.1", "1.0.0"))
        self.assertTrue(is_newer_version("1.1.0", "1.0.9"))
        self.assertTrue(is_newer_version("10.0.0", "9.9.9"))


class TestCliModule(unittest.TestCase):
    def test_commands_list(self):
        from pilotstd.cli.commands import __all__ as cmds
        self.assertIsInstance(cmds, (list, tuple))

    def test_shared_make_manager(self):
        from pilotstd.cli.commands._shared import _make_manager
        self.assertTrue(callable(_make_manager))


class TestOrganizerModule(unittest.TestCase):
    def test_mover_import(self):
        from pilotstd.organizer.mover import FileMover
        self.assertTrue(hasattr(FileMover, '__init__'))

    def test_dir_builder_root(self):
        import tempfile, shutil
        from pilotstd.organizer.dir_builder import DirBuilder
        tmp = tempfile.mkdtemp()
        try:
            db = DirBuilder(tmp)
            self.assertEqual(db.root, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
