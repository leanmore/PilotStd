"""tests/test_db_migration_lock_loop.py — 迁移锁获取不得死循环（NEW-02，2026-11-23）。

背景：`_acquire_migration_lock` 在 `except FileExistsError` 分支里，
清理陈旧锁失败时执行 `except OSError: continue` —— 这会**跳过下面的超时判断**
直接回到 `while True`。一旦锁文件持续不可读（权限/占用/路径异常），
就变成死循环、永不返回 `False`，调用方永远拿不到"拿不到锁"的结论。

修法：清理失败只记录并落到超时判断，不 continue。

本测试锁住：锁文件存在但不可读时，函数必须在超时内返回 False，而不是挂死。
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.core.db.database import Database  # noqa: E402


def test_lock_unreadable_returns_false_within_timeout(tmp_path):
    """锁文件存在但 getmtime 一直抛 OSError ⇒ 必须在超时内返回 False。"""
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    lock_path = db_path + ".migration_lock"
    # 先造出一个"已存在"的锁文件，让首次 os.open 抛 FileExistsError
    Path(lock_path).write_text("12345", encoding="utf-8")

    # `getmtime` 永远抛 OSError（模拟权限不足/文件被占用）
    with patch("pilotstd.core.db.database.os.path.getmtime", side_effect=OSError("denied")):
        started = time.time()
        got = db._acquire_migration_lock(timeout=2.0)
        elapsed = time.time() - started

    assert got is False, "锁不可读时必须返回 False（拿不到锁），不能死循环"
    # 超时 2s + 最多一次 sleep(0.5)，给足余量但不允许无限等
    assert elapsed < 10.0, f"耗时 {elapsed:.1f}s，疑似仍在循环（预期 ≤ 2.5s 量级）"


def test_lock_acquired_when_absent(tmp_path):
    """正常路径：锁不存在时能拿到锁。"""
    db_path = str(tmp_path / "test2.db")
    db = Database(db_path)
    assert db._acquire_migration_lock(timeout=2.0) is True
    assert Path(db_path + ".migration_lock").exists()
    db._release_migration_lock()
    assert not Path(db_path + ".migration_lock").exists()


def test_stale_lock_is_cleaned_and_acquired(tmp_path):
    """陈旧锁（mtime 超阈值）应被清理并成功获取。"""
    db_path = str(tmp_path / "test3.db")
    db = Database(db_path)
    lock_path = db_path + ".migration_lock"
    Path(lock_path).write_text("99999", encoding="utf-8")

    # 把 `mtime` 伪造到很久以前
    old = time.time() - 3600
    import os

    os.utime(lock_path, (old, old))

    assert db._acquire_migration_lock(timeout=2.0) is True
    db._release_migration_lock()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
