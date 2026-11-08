# tests/test_migrate_v56_cache_columns.py — v56 补列失败必须抛出且带堆栈
"""验证 v56：PRAGMA/ALTER 失败时不得静默吞错（D-1 根因回归）。

- PRAGMA 读取失败 → 抛异常，日志带 exc_info（堆栈）；
- ALTER 失败 → 抛异常，日志带 exc_info；
- 表不存在 → 跳过，不抛（新库路径）；
- 正常库 → 三列补齐。
"""

import logging
import sqlite3

import pytest

from pilotstd.core.db._migrate_v56 import _migrate_v56_ensure_cache_version_columns


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


class _PragmaBrokenDb(_FakeDb):
    """PRAGMA 读取必失败，模拟表结构不可读。"""

    def fetchall(self, sql: str, params: tuple = ()):
        if sql.strip().upper().startswith("PRAGMA"):
            raise RuntimeError("pragma boom")
        return super().fetchall(sql, params)


class _AlterBrokenDb(_FakeDb):
    """ALTER TABLE 必失败，模拟补列异常。"""

    def execute(self, sql: str, params: tuple = ()):
        if sql.strip().upper().startswith("ALTER TABLE"):
            raise RuntimeError("alter boom")
        return super().execute(sql, params)


def test_pragma_failure_raises_with_stack(caplog) -> None:
    """PRAGMA 失败 → RuntimeError 上抛，日志记录 exc_info。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tmp_standard_info_cache (id INTEGER PRIMARY KEY)")
    conn.execute("ALTER TABLE tmp_standard_info_cache RENAME TO standard_info_cache")
    db = _PragmaBrokenDb(conn)

    with caplog.at_level(logging.ERROR, logger="pilotstd.db.migrate.v56"):
        with pytest.raises(RuntimeError, match="pragma boom"):
            _migrate_v56_ensure_cache_version_columns(db)

    assert any(r.exc_info is not None for r in caplog.records), "失败日志必须带堆栈"


def test_alter_failure_raises_with_stack(caplog) -> None:
    """ALTER 失败 → RuntimeError 上抛，日志记录 exc_info。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tmp_standard_info_cache (id INTEGER PRIMARY KEY)")
    conn.execute("ALTER TABLE tmp_standard_info_cache RENAME TO standard_info_cache")
    db = _AlterBrokenDb(conn)

    with caplog.at_level(logging.ERROR, logger="pilotstd.db.migrate.v56"):
        with pytest.raises(RuntimeError, match="alter boom"):
            _migrate_v56_ensure_cache_version_columns(db)

    assert any(r.exc_info is not None for r in caplog.records), "失败日志必须带堆栈"


def test_missing_tables_are_skipped() -> None:
    """表不存在 → 跳过，不抛异常（新库路径）。"""
    db = _new_db()
    _migrate_v56_ensure_cache_version_columns(db)  # 不应抛


def test_adds_missing_columns_and_is_idempotent() -> None:
    """正常库：三列补齐；再跑一次不重复 ALTER。"""
    db = _new_db()
    db.execute("CREATE TABLE tmp_standard_info_cache (id INTEGER PRIMARY KEY)")
    db.execute("ALTER TABLE tmp_standard_info_cache RENAME TO standard_info_cache")

    _migrate_v56_ensure_cache_version_columns(db)
    _migrate_v56_ensure_cache_version_columns(db)

    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    assert {"source_version", "data_state", "last_accessed_at"} <= cols
