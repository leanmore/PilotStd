# tests/test_organizer.py

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import shutil
import tempfile
import unittest

from pilotstd.models import ParsedStdInfo
from pilotstd.organizer.dir_builder import DirBuilder
from pilotstd.organizer.expire_handler import ExpireHandler
from pilotstd.organizer.industry_lookup import (
    INDUSTRY_MAP,
    get_base_code,
    get_folder_name,
    get_industry_name,
)
from pilotstd.organizer.mover import FileMover


class TestIndustryLookup(unittest.TestCase):
    def test_get_base_code_gbt(self):
        self.assertEqual(get_base_code("GB/T"), "GB")
        self.assertEqual(get_base_code("SH/T"), "SH")
        self.assertEqual(get_base_code("GB/Z"), "GB")

    def test_get_industry_name(self):
        self.assertEqual(get_industry_name("GB"), "国家标准")
        self.assertEqual(get_industry_name("AQ"), "安全生产")
        self.assertEqual(get_industry_name("YD"), "通信")

    def test_get_industry_name_unknown(self):
        self.assertIn("未知", get_industry_name("XX"))

    def test_get_folder_name(self):
        self.assertEqual(get_folder_name("GB/T"), "GB 国家标准")
        self.assertEqual(get_folder_name("SH/T"), "SH 石油化工")

    def test_map_coverage(self):
        self.assertGreater(len(INDUSTRY_MAP), 60)


class TestDirBuilder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.builder = DirBuilder(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_ensure_code_dir_creates(self):
        path = self.builder.ensure_code_dir("GB/T")
        self.assertTrue(os.path.isdir(path))
        self.assertIn("GB 国家标准", path)

    def test_ensure_expire_dir(self):
        path = self.builder.ensure_expire_dir("SH/T")
        self.assertTrue(os.path.isdir(path))
        self.assertIn("过期作废", path)

    def test_get_expire_dir_no_create(self):
        path = self.builder.ensure_expire_dir("GB/T")
        self.assertTrue(os.path.isdir(path))


class TestFileMover(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.builder = DirBuilder(self.tmp)
        self.mover = FileMover(self.builder)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_move_to_code_dir(self):
        src = os.path.join(self.tmp, "test.pdf")
        with open(src, "w") as f:
            f.write("dummy")
        parsed = ParsedStdInfo(
            raw_filename="test.pdf",
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="测试",
        )
        dst = self.mover.move_to_code_dir(src, parsed)
        self.assertIsNotNone(dst)
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(src))
        self.assertIn("GBT", os.path.basename(dst))

    def test_is_safe_path_accepts_internal(self):
        """库根目录内的路径通过校验。"""
        self.assertTrue(self.mover._is_safe_path(os.path.join(self.tmp, "sub", "file.pdf")))

    def test_is_safe_path_rejects_escape(self):
        """库根目录外的路径被拒绝。"""
        parent = os.path.dirname(self.tmp)
        self.assertFalse(self.mover._is_safe_path(os.path.join(parent, "escape.pdf")))

    def test_move_to_code_dir_rejects_outside_path(self):
        """目标路径越界时 move_to_code_dir 返回 None。（通过 mock normalize 模拟）"""
        src = os.path.join(self.tmp, "test.pdf")
        with open(src, "w") as f:
            f.write("dummy")
        # 让 normalize_filename 返回根目录外路径
        original = self.mover.normalize_filename
        outside = os.path.join(os.path.dirname(self.tmp), "escaped.pdf")
        self.mover.normalize_filename = lambda parsed: outside
        try:
            dst = self.mover.move_to_code_dir(
                src,
                ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=1, year=2020),
            )
            self.assertIsNone(dst, "越界路径应被拒绝返回 None")
        finally:
            self.mover.normalize_filename = original

    def test_move_to_expire(self):
        src = os.path.join(self.tmp, "old.pdf")
        with open(src, "w") as f:
            f.write("old")
        parsed = ParsedStdInfo(raw_filename="old.pdf", logical_code="GB", number=1234, year=1986)
        dst = self.mover.move_to_expire(src, parsed)
        self.assertIsNotNone(dst)
        self.assertTrue(os.path.exists(dst))
        self.assertIn("过期作废", dst)


class TestExpireHandler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.builder = DirBuilder(self.tmp)
        self.mover = FileMover(self.builder)
        self.handler = ExpireHandler(self.mover)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_process_expired(self):
        src = os.path.join(self.tmp, "expired.pdf")
        with open(src, "w") as f:
            f.write("data")
        parsed = ParsedStdInfo(raw_filename="expired.pdf", logical_code="GB", number=1, year=1990)
        result = self.handler.process_expired([(src, parsed)])
        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["failed"], 0)

    def test_process_missing_file(self):
        parsed = ParsedStdInfo(raw_filename="ghost.pdf", logical_code="GB", number=2, year=1995)
        result = self.handler.process_expired([(os.path.join(self.tmp, "ghost.pdf"), parsed)])
        self.assertEqual(result["failed"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
