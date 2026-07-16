# tests/gui/test_cleanup_flow_engine.py
"""CleanupFlowEngine 单元测试 — 纯 Python，不启动 QApplication，无需文件系统。

直接构造 dir_tree 字典和文件路径列表，微秒级完成。
覆盖 scan_empty_dirs 和 build_unrecognized_tree 的：
- 正常路径
- 边界值（空字典、空列表、无匹配）
- 排除模式
- 异常容错（错误类型输入）
"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.cleanup_flow_engine import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_EXPIRE_FOLDER,
    MAX_DEPTH,
    CleanupFlowEngine,
)


@pytest.fixture
def engine() -> CleanupFlowEngine:
    return CleanupFlowEngine()


# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════


class TestConstants:
    def test_default_exclude_patterns(self):
        assert ".DS_Store" in DEFAULT_EXCLUDE_PATTERNS
        assert "Thumbs.db" in DEFAULT_EXCLUDE_PATTERNS

    def test_default_expire_folder(self):
        assert DEFAULT_EXPIRE_FOLDER == "过期作废"

    def test_max_depth(self):
        assert MAX_DEPTH == 1000


# ═══════════════════════════════════════════════════════════════════
# scan_empty_dirs
# ═══════════════════════════════════════════════════════════════════


class TestScanEmptyDirs:
    def test_empty_dirs(self, engine):
        dir_tree = {
            "/root/empty_A": [],
            "/root/empty_B": [],
            "/root/non_empty": ["file.txt", "subdir"],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert sorted(empty) == ["/root/empty_A", "/root/empty_B"]
        assert expire == []

    def test_expire_only(self, engine):
        dir_tree = {
            "/root/std_dir": ["过期作废"],
            "/root/empty": [],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert empty == ["/root/empty"]
        assert expire == ["/root/std_dir"]

    def test_expire_only_with_garbage(self, engine):
        """排除系统文件后，仅剩过期文件夹 → 归入 expire_only。"""
        dir_tree = {
            "/root/std_dir": [".DS_Store", "过期作废"],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert empty == []
        assert expire == ["/root/std_dir"]

    def test_empty_after_exclusion(self, engine):
        """排除系统文件后无子项 → 归入空目录。"""
        dir_tree = {
            "/root/only_garbage": [".DS_Store", "Thumbs.db"],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert empty == ["/root/only_garbage"]
        assert expire == []

    def test_custom_expire_name(self, engine):
        dir_tree = {
            "/root/dir_a": ["旧版废止"],
            "/root/dir_b": ["过期作废"],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree, expire_folder_name="旧版废止")
        assert empty == []
        assert expire == ["/root/dir_a"]

    def test_custom_exclude_patterns(self, engine):
        dir_tree = {
            "/root/dir": ["custom_garbage.txt"],
        }
        empty, expire = engine.scan_empty_dirs(
            dir_tree, exclude_patterns=["custom_garbage.txt"]
        )
        assert empty == ["/root/dir"]

    def test_empty_tree(self, engine):
        empty, expire = engine.scan_empty_dirs({})
        assert empty == []
        assert expire == []

    def test_none_tree(self, engine):
        empty, expire = engine.scan_empty_dirs(None)  # type: ignore[arg-type]
        assert empty == []
        assert expire == []

    def test_non_dict_tree(self, engine):
        empty, expire = engine.scan_empty_dirs("not_a_dict")  # type: ignore[arg-type]
        assert empty == []
        assert expire == []

    def test_children_not_list(self, engine):
        """子项不是列表 → 跳过该目录。"""
        dir_tree = {
            "/root/bad": "not_a_list",  # type: ignore[dict-item]
            "/root/empty": [],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert empty == ["/root/empty"]

    def test_two_children_not_expire(self, engine):
        """有两个子项但都不是排除模式 → 不归入任何类别。"""
        dir_tree = {
            "/root/dir": ["过期作废", "other_file.txt"],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert empty == []
        assert expire == []

    def test_deep_paths(self, engine):
        dir_tree = {
            "/a/b/c/d/e": [],
            "/a/b/c/d/f": ["file.txt"],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert empty == ["/a/b/c/d/e"]

    def test_multiple_expire_only(self, engine):
        dir_tree = {
            "/root/gb1": ["过期作废"],
            "/root/gb2": ["过期作废"],
            "/root/normal": ["file.txt"],
        }
        empty, expire = engine.scan_empty_dirs(dir_tree)
        assert len(expire) == 2
        assert "/root/gb1" in expire
        assert "/root/gb2" in expire


# ═══════════════════════════════════════════════════════════════════
# build_unrecognized_tree
# ═══════════════════════════════════════════════════════════════════


class TestBuildUnrecognizedTree:
    def test_normal(self, engine):
        files = [
            "/path/a.pdf",
            "/path/b.pdf",
            "/path/c.txt",
            "/path/d.doc",
        ]
        result = engine.build_unrecognized_tree(files)
        assert result == {
            ".doc": ["/path/d.doc"],
            ".pdf": ["/path/a.pdf", "/path/b.pdf"],
            ".txt": ["/path/c.txt"],
        }

    def test_empty_list(self, engine):
        assert engine.build_unrecognized_tree([]) == {}

    def test_single_file(self, engine):
        result = engine.build_unrecognized_tree(["/tmp/file.pdf"])
        assert result == {".pdf": ["/tmp/file.pdf"]}

    def test_no_extension(self, engine):
        files = ["/path/README", "/path/Makefile"]
        result = engine.build_unrecognized_tree(files)
        assert result == {"": ["/path/README", "/path/Makefile"]}

    def test_mixed_case_extension(self, engine):
        """后缀统一为小写。"""
        files = ["/a/file.PDF", "/b/file.pdf", "/c/file.Pdf"]
        result = engine.build_unrecognized_tree(files)
        assert result == {".pdf": ["/a/file.PDF", "/b/file.pdf", "/c/file.Pdf"]}

    def test_known_extensions_filtered(self, engine):
        files = ["/a/file.pdf", "/b/file.doc", "/c/file.txt", "/d/notes.txt"]
        result = engine.build_unrecognized_tree(files, known_extensions={".pdf", ".doc"})
        assert ".pdf" not in result
        assert ".doc" not in result
        assert result == {".txt": ["/c/file.txt", "/d/notes.txt"]}

    def test_all_known_extensions(self, engine):
        files = ["/a/file.pdf", "/b/file.doc"]
        result = engine.build_unrecognized_tree(files, known_extensions={".pdf", ".doc"})
        assert result == {}

    def test_none_files(self, engine):
        result = engine.build_unrecognized_tree(None)  # type: ignore[arg-type]
        assert result == {}

    def test_non_list_files(self, engine):
        result = engine.build_unrecognized_tree("not_a_list")  # type: ignore[arg-type]
        assert result == {}

    def test_non_str_items_skipped(self, engine):
        files = ["/a/file.pdf", None, 123, "/b/file.txt"]  # type: ignore[list-item]
        result = engine.build_unrecognized_tree(files)
        assert result == {".pdf": ["/a/file.pdf"], ".txt": ["/b/file.txt"]}

    def test_result_is_sorted_by_key(self, engine):
        files = ["/a/z.txt", "/b/a.pdf", "/c/m.doc"]
        result = engine.build_unrecognized_tree(files)
        keys = list(result.keys())
        assert keys == sorted(keys)

    def test_windows_paths(self, engine):
        files = [
            "C:\\Users\\test\\file.pdf",
            "D:\\docs\\readme.txt",
        ]
        result = engine.build_unrecognized_tree(files)
        assert result == {".pdf": ["C:\\Users\\test\\file.pdf"], ".txt": ["D:\\docs\\readme.txt"]}
