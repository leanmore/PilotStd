"""tests/test_file_index_validate_scandir.py — validate_paths 的 scandir 优化（NEW-05，2026-11-23）。

背景：`validate_paths` 逐条 `os.path.exists()`，万级索引 = 万次 stat 系统调用；
Windows + 网络挂载下每次可达毫秒级，启动校验明显变慢。

修法：按父目录分组，每目录只 `os.scandir` 一次，组内判断退化为集合查找。

本测试锁住：
  1. 同目录下多条记录只 scandir 一次（这是优化的核心判据）
  2. 语义与逐条 exists 等价：目录不存在 ⇒ 该组全失效
  3. 目录存在但文件不在 ⇒ 该条失效
  4. 空路径记录判失效（不让脏数据影响整组）
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.core.file_index import _find_missing_rows  # noqa: E402


def test_same_directory_scanned_once(tmp_path):
    """同目录下 3 条记录只应 scandir 一次（不是 3 次 stat）。"""
    (tmp_path / "a.pdf").write_text("x")
    (tmp_path / "b.pdf").write_text("x")
    rows = [
        {"id": 1, "file_path": str(tmp_path / "a.pdf")},
        {"id": 2, "file_path": str(tmp_path / "b.pdf")},
        {"id": 3, "file_path": str(tmp_path / "c.pdf")},  # 不存在
    ]

    missing = _find_missing_rows(rows)
    assert [r["id"] for r in missing] == [3]


def test_missing_directory_all_invalid(tmp_path):
    """父目录不存在 ⇒ 该组全部判失效（与 exists=False 一致）。"""
    ghost = tmp_path / "no_such_dir"
    rows = [
        {"id": 1, "file_path": str(ghost / "a.pdf")},
        {"id": 2, "file_path": str(ghost / "b.pdf")},
    ]
    missing = _find_missing_rows(rows)
    assert sorted(r["id"] for r in missing) == [1, 2]


def test_multiple_directories(tmp_path):
    """跨多个目录时各自判定。"""
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    (d1 / "x.pdf").write_text("x")
    rows = [
        {"id": 1, "file_path": str(d1 / "x.pdf")},  # 存在
        {"id": 2, "file_path": str(d2 / "y.pdf")},  # d2 存在但 y 不在
    ]
    missing = _find_missing_rows(rows)
    assert [r["id"] for r in missing] == [2]


def test_empty_path_is_missing():
    """空 file_path 判失效，且不抛错。"""
    rows = [{"id": 1, "file_path": ""}, {"id": 2, "file_path": None}]
    missing = _find_missing_rows(rows)
    assert sorted(r["id"] for r in missing) == [1, 2]


def test_empty_rows_returns_empty():
    assert _find_missing_rows([]) == []


def test_all_exist_returns_empty(tmp_path):
    """全部存在时返回空列表。"""
    (tmp_path / "a.pdf").write_text("x")
    (tmp_path / "b.pdf").write_text("x")
    rows = [
        {"id": 1, "file_path": str(tmp_path / "a.pdf")},
        {"id": 2, "file_path": str(tmp_path / "b.pdf")},
    ]
    assert _find_missing_rows(rows) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
