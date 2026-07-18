# tests/test_group1_complete.py — 第一组：organizer/models/quality 补完

import os
import sys
import tempfile
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

_CI = os.environ.get("CI", "").lower() in ("true", "1")


class TestModelsComplete(unittest.TestCase):
    def test_parsed_std_info_all_fields(self):
        from pilotstd.models import ParsedStdInfo

        info = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB/T",
            number=1,
            year=2020,
            std_name="Test",
            part=1,
            ext=".pdf",
            language="zh",
            file_kind="standard",
            source_path="/tmp/test.pdf",
        )
        self.assertEqual(info.logical_code, "GB/T")
        self.assertEqual(info.year, 2020)


class TestQualityRunnerComplete(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_on_py_file(self):
        from pilotstd.quality.rules.stale_references import StaleReferencesRule
        from pilotstd.quality.runner import QualityRunner

        rule = StaleReferencesRule()
        runner = QualityRunner(rules=[rule])
        py_file = os.path.join(self.tmpdir, "test.py")
        with open(py_file, "w") as f:
            f.write("print('hello')\n")
        report = runner.run([py_file])
        self.assertEqual(report.files_checked, 1)

    def test_run_on_directory(self):
        from pilotstd.quality.rules.stale_references import StaleReferencesRule
        from pilotstd.quality.runner import QualityRunner

        py_file = os.path.join(self.tmpdir, "sample.py")
        with open(py_file, "w") as f:
            f.write("x = 1\n")
        runner = QualityRunner(rules=[StaleReferencesRule()])
        report = runner.run([self.tmpdir])
        self.assertGreaterEqual(report.files_checked, 1)

    def test_run_skips_non_py_files(self):
        from pilotstd.quality.runner import QualityRunner

        txt_file = os.path.join(self.tmpdir, "readme.txt")
        with open(txt_file, "w") as f:
            f.write("hello")
        runner = QualityRunner(rules=[])
        report = runner.run([txt_file])
        self.assertEqual(report.files_checked, 0)


class TestStaleReferencesComplete(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_file_no_violations(self):
        from pilotstd.quality.rules.stale_references import StaleReferencesRule

        rule = StaleReferencesRule()
        f = os.path.join(self.tmpdir, "clean.py")
        with open(f, "w") as fh:
            fh.write("import os\nprint('ok')\n")
        violations = rule.check_file(f)
        self.assertEqual(violations, [])

    def test_check_file_with_stale_import(self):
        from pilotstd.quality.rules.stale_references import StaleReferencesRule

        rule = StaleReferencesRule()
        f = os.path.join(self.tmpdir, "stale.py")
        with open(f, "w") as fh:
            fh.write("from pilotstd.query.search_strategy import build_search_terms\n")
        violations = rule.check_file(f)
        self.assertGreater(len(violations), 0)
        self.assertEqual(violations[0].rule, "stale-references")

    def test_check_file_with_stale_attribute(self):
        from pilotstd.quality.rules.stale_references import StaleReferencesRule

        rule = StaleReferencesRule()
        f = os.path.join(self.tmpdir, "stale_attr.py")
        with open(f, "w") as fh:
            fh.write("result = obj.build_search_terms()\n")
        violations = rule.check_file(f)
        self.assertGreater(len(violations), 0)

    def test_check_file_syntax_error(self):
        from pilotstd.quality.rules.stale_references import StaleReferencesRule

        rule = StaleReferencesRule()
        f = os.path.join(self.tmpdir, "bad.py")
        with open(f, "w") as fh:
            fh.write("this is not valid python {{{{{\n")
        violations = rule.check_file(f)
        self.assertEqual(violations, [])

    def test_quality_models(self):
        from pilotstd.quality.models import CheckReport, Severity, Violation

        v = Violation(rule="test", severity=Severity.ERROR, file="f.py", line=1, message="msg")
        self.assertEqual(v.severity, Severity.ERROR)
        r = CheckReport()
        r.violations.append(v)
        self.assertEqual(len(r.violations), 1)


class TestFileMoverComplete(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from pilotstd.organizer.dir_builder import DirBuilder

        self.db = DirBuilder(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_is_safe_path_true(self):
        from pilotstd.organizer.mover import FileMover

        fm = FileMover(self.db)
        target = os.path.join(self.tmpdir, "subdir", "file.pdf")
        self.assertTrue(fm._is_safe_path(target))

    def test_is_safe_path_false(self):
        from pilotstd.organizer.mover import FileMover

        fm = FileMover(self.db)
        self.assertFalse(fm._is_safe_path("/etc/passwd"))

    def test_normalize_filename(self):
        from pilotstd.models import ParsedStdInfo
        from pilotstd.organizer.mover import FileMover

        fm = FileMover(self.db)
        info = ParsedStdInfo(
            raw_filename="test.pdf", logical_code="GB/T", number=1, year=2020, std_name="Test", ext=".pdf"
        )
        path = fm.normalize_filename(info)
        self.assertIn("GB", path)

    def test_normalize_expired(self):
        from pilotstd.models import ParsedStdInfo
        from pilotstd.organizer.mover import FileMover

        fm = FileMover(self.db)
        info = ParsedStdInfo(
            raw_filename="test.pdf", logical_code="GB/T", number=1, year=2020, std_name="Test", ext=".pdf"
        )
        info.effect_status = "废止"
        path = fm.normalize_filename(info)
        self.assertIn("过期作废", path)

    @unittest.skipIf(_CI, "CI 环境文件权限问题待排查")
    def test_archive(self):
        from pilotstd.organizer.mover import FileMover

        src = os.path.join(self.tmpdir, "src.txt")
        dst = os.path.join(self.tmpdir, "dst.txt")
        with open(src, "w") as f:
            f.write("test")
        fm = FileMover(self.db)
        result = fm.archive(src, dst)
        self.assertEqual(result, dst)
        self.assertTrue(os.path.exists(dst))

    @unittest.skipIf(_CI, "CI 环境文件权限问题待排查")
    def test_move_to_code_dir(self):
        from pilotstd.models import ParsedStdInfo
        from pilotstd.organizer.mover import FileMover

        src = os.path.join(self.tmpdir, "test.pdf")
        with open(src, "w") as f:
            f.write("test")
        fm = FileMover(self.db)
        info = ParsedStdInfo(
            raw_filename="test.pdf", logical_code="GB/T", number=1, year=2020, std_name="Test", ext=".pdf"
        )
        result = fm.move_to_code_dir(src, info)
        self.assertIsNotNone(result)

    @unittest.skipIf(_CI, "CI 环境文件权限问题待排查")
    def test_move_to_expire(self):
        from pilotstd.models import ParsedStdInfo
        from pilotstd.organizer.mover import FileMover

        src = os.path.join(self.tmpdir, "old.pdf")
        with open(src, "w") as f:
            f.write("test")
        fm = FileMover(self.db)
        info = ParsedStdInfo(
            raw_filename="test.pdf", logical_code="GB/T", number=1, year=2000, std_name="Old", ext=".pdf"
        )
        result = fm.move_to_expire(src, info)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
