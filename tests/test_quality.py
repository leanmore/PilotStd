# tests/test_quality.py
# 质量检查工具测试

import unittest
import tempfile
import os
import shutil

from pilotstd.quality.models import CheckReport, Violation, Severity
from pilotstd.quality.rules.stale_references import StaleReferencesRule
from pilotstd.quality.runner import QualityRunner


class TestStaleReferencesRule(unittest.TestCase):
    def setUp(self):
        self.rule = StaleReferencesRule()
        self.tmp = tempfile.mkdtemp(prefix="quality_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_detects_import_of_deleted_symbol(self):
        path = self._write("test_mod.py",
            "from pilotstd.query.search_strategy import build_search_terms\n")
        violations = self.rule.check_file(path)
        self.assertEqual(len(violations), 1)
        self.assertIn("build_search_terms", violations[0].message)

    def test_detects_method_call_on_deleted_api(self):
        path = self._write("test_mod.py",
            "adapter.query_single('GB/T 1-2020')\n")
        violations = self.rule.check_file(path)
        self.assertEqual(len(violations), 1)
        self.assertIn("query_single", violations[0].message)

    def test_clean_file_no_violations(self):
        path = self._write("test_mod.py",
            "from pilotstd.query.search_strategy import build_code_variants\n"
            "adapter.query_with_strategy('GB/T', 1, 2020)\n")
        violations = self.rule.check_file(path)
        self.assertEqual(len(violations), 0)

    def test_runner_scans_directory(self):
        self._write("a.py",
            "from pilotstd.query.search_strategy import build_search_terms\n")
        self._write("b.py",
            "adapter.query_single('test')\n")
        runner = QualityRunner()
        report = runner.run([self.tmp])
        self.assertGreaterEqual(len(report.violations), 2)
        self.assertFalse(report.passed)
