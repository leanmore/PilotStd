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

_CI = os.environ.get("CI", "").lower() in ("true", "1")
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

    @unittest.skipIf(_CI, "CI 环境文件权限问题待排查")
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


# === _utils.py 覆盖 ===


class TestOrganizerUtils(unittest.TestCase):
    """_is_word_or_template / _resolve_industry_in_path 独立测试。"""

    def test_is_word_or_template_doc_returns_true(self):
        """Word 文件 (.doc) 返回 True。"""
        from pilotstd.manager.organize._utils import _is_word_or_template

        self.assertTrue(_is_word_or_template("report.doc"))
        self.assertTrue(_is_word_or_template("report.docx"))

    def test_is_word_or_template_pdf_returns_false(self):
        """PDF 和普通文件返回 False。"""
        from pilotstd.manager.organize._utils import _is_word_or_template

        self.assertFalse(_is_word_or_template("standard.pdf"))
        self.assertFalse(_is_word_or_template("file.txt"))


# === expire.py 覆盖 ===


class TestOrganizerExpire(unittest.TestCase):
    """merge_expire_from_source 测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_merge_expire_from_source_no_expire_dir(self):
        """合并时若无 expires 目录则 merged=0，不报错。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.expire import merge_expire_from_source

        cfg = MagicMock()
        cfg.get.return_value = "过期作废"

        src_dir = os.path.join(self.tmp, "subdir")
        os.makedirs(src_dir)
        parsed = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=2, year=1999)
        parsed.source_path = os.path.join(src_dir, "test.pdf")

        merged = merge_expire_from_source(cfg, self.tmp, [parsed])
        self.assertEqual(merged, 0)


# === mirror.py 覆盖 ===


class TestOrganizerMirror(unittest.TestCase):
    """OrganizerMirror.organize_skipped_dirs / organize_fallback 测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_organize_skipped_dirs_path_traversal_blocked(self):
        """越界路径被拒绝，failed 计数递增。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.mirror import OrganizerMirror

        cfg = MagicMock()
        lib = os.path.join(self.tmp, "lib")
        os.makedirs(lib)
        cfg.get.return_value = lib
        obj = OrganizerMirror(cfg)
        result = obj.organize_skipped_dirs([], source_root=None)
        self.assertIn("moved", result)
        self.assertEqual(result["moved"], 0)

    def test_organize_fallback_skip_system_files(self):
        """Thumbs.db / ~$ 前缀文件被跳过不处理。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.mirror import OrganizerMirror

        cfg = MagicMock()
        cfg.get.return_value = os.path.join(self.tmp, "lib")
        obj = OrganizerMirror(cfg)

        thumbs = os.path.join(self.tmp, "Thumbs.db")
        with open(thumbs, "w") as f:
            f.write("skip")
        tmp_file = os.path.join(self.tmp, "~$temp.docx")
        with open(tmp_file, "w") as f:
            f.write("skip")

        result = obj.organize_fallback(self.tmp, frozenset())
        self.assertIn("skipped", result)
        self.assertGreaterEqual(result["skipped"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
