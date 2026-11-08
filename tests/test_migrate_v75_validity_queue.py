# tests/test_migrate_v75_validity_queue.py — v75 建时效性检查队列
"""验证 v75：validity_check_queue 建表 + 索引（1 普通 + 1 唯一部分索引）。

注：工单写「2 个唯一索引」，实际代码是 1 个普通索引 + 1 个唯一部分索引
（`WHERE status='pending'`）——本文件按代码事实断言。
"""

import sqlite3

from pilotstd.core.db._migrate_v75_validity_queue import _migrate_v75_validity_queue


class _FakeDb:
    """把 sqlite3.Connection 适配成迁移所需的 Database 接口。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchall()


def _new_db() -> _FakeDb:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return _FakeDb(conn)


def test_creates_queue_table_with_expected_columns() -> None:
    """空库 → 表存在且列齐全。"""
    db = _new_db()
    _migrate_v75_validity_queue(db)

    assert db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='validity_check_queue'"
    )
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(validity_check_queue)")}
    assert {"id", "file_path", "status", "error", "created_at", "updated_at"} <= cols


def test_creates_two_indexes() -> None:
    """status 普通索引 + pending 唯一部分索引。"""
    db = _new_db()
    _migrate_v75_validity_queue(db)

    indexes = {
        r["name"]: (r["sql"] or "")
        for r in db.fetchall(
            "SELECT name, sql FROM sqlite_master"
            " WHERE type='index' AND tbl_name='validity_check_queue'"
        )
    }
    assert "idx_validity_queue_status" in indexes
    unique_sql = indexes.get("idx_validity_queue_pending_unique", "")
    assert "UNIQUE" in unique_sql.upper()
    assert "status='pending'" in unique_sql.replace(" ", "").replace('"', "'")


def test_pending_duplicate_rejected_but_retry_allowed() -> None:
    """同一 file_path 只能有一行 pending；失败后（非 pending）可再入队。"""
    db = _new_db()
    _migrate_v75_validity_queue(db)
    insert = (
        "INSERT INTO validity_check_queue (file_path, status, created_at, updated_at)"
        " VALUES (?, ?, 't', 't')"
    )
    db.execute(insert, ("/a.pdf", "pending"))
    try:
        db.execute(insert, ("/a.pdf", "pending"))
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("重复 pending 未被唯一索引拦截")

    db.execute("UPDATE validity_check_queue SET status='failed' WHERE file_path='/a.pdf'")
    db.execute(insert, ("/a.pdf", "pending"))  # 允许重试
    assert db.fetchone(
        "SELECT COUNT(*) AS c FROM validity_check_queue WHERE file_path='/a.pdf'"
    )["c"] == 2


def test_rerun_is_idempotent() -> None:
    """重跑不报错（IF NOT EXISTS）。"""
    db = _new_db()
    _migrate_v75_validity_queue(db)
    _migrate_v75_validity_queue(db)
