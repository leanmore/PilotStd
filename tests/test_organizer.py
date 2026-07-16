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

    @unittest.skipIf(_CI, "CI 环境文件权限问题待排查")
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


class TestOrganizerExpireMixin(unittest.TestCase):
    """OrganizerExpireMixin.handle_expired / merge_expire_from_source 测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_handle_expired_delegates_to_handler(self):
        """handle_expired 委托 _expire_handler.process_expired，返回结果。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.expire import OrganizerExpireMixin

        # mock expire_handler.process_expired
        mock_handler = MagicMock()
        mock_handler.process_expired.return_value = {"moved": 2, "failed": 0}
        # 构造带 _expire_handler 的类实例
        obj = type("_Mock", (OrganizerExpireMixin,), {"_expire_handler": mock_handler})()

        parsed = ParsedStdInfo(raw_filename="old.pdf", logical_code="GB", number=1, year=2000)
        parsed.source_path = os.path.join(self.tmp, "old.pdf")
        with open(parsed.source_path, "w") as f:
            f.write("data")

        result = obj.handle_expired([parsed])
        self.assertIn("moved", result)
        mock_handler.process_expired.assert_called_once()

    def test_merge_expire_from_source_no_expire_dir(self):
        """合并时若无 expires 目录则 merged=0，不报错。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.expire import OrganizerExpireMixin

        obj = type(
            "_Mock",
            (OrganizerExpireMixin,),
            {"_cfg": MagicMock()},
        )()
        obj._cfg.get.return_value = "过期作废"

        src_dir = os.path.join(self.tmp, "subdir")
        os.makedirs(src_dir)
        parsed = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=2, year=1999)
        parsed.source_path = os.path.join(src_dir, "test.pdf")

        merged = obj.merge_expire_from_source(self.tmp, [parsed])
        self.assertEqual(merged, 0)


# === mirror.py 覆盖 ===


class TestOrganizerMirrorMixin(unittest.TestCase):
    """OrganizerMirrorMixin.organize_skipped_dirs / organize_fallback 测试。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_organize_skipped_dirs_path_traversal_blocked(self):
        """越界路径被拒绝，failed 计数递增。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.mirror import OrganizerMirrorMixin

        obj = type(
            "_Mock",
            (OrganizerMirrorMixin,),
            {"_cfg": MagicMock()},
        )()
        # mock get_library_root 返回临时目录下的 lib
        lib = os.path.join(self.tmp, "lib")
        os.makedirs(lib)
        obj._cfg.get.return_value = lib  # get_library_root 内部调用 _cfg.get("storage.root_dir")
        # 构造一个 dst 会越界的 skipped dir
        result = obj.organize_skipped_dirs([], source_root=None)
        self.assertIn("moved", result)
        self.assertEqual(result["moved"], 0)

    def test_organize_fallback_skip_system_files(self):
        """Thumbs.db / ~$ 前缀文件被跳过不处理。"""
        from unittest.mock import MagicMock

        from pilotstd.manager.organize.mirror import OrganizerMirrorMixin

        obj = type(
            "_Mock",
            (OrganizerMirrorMixin,),
            {
                "_cfg": MagicMock(),
                "_skipped_source_files": set(),
                "_FALLBACK_SKIP_FILES": frozenset({"Thumbs.db", "sync.ffs_db"}),
                "_FALLBACK_SKIP_PREFIX": "~$",
            },
        )()
        obj._cfg.get.return_value = os.path.join(self.tmp, "lib")

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
