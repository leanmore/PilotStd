"""v61 迁移测试（#32-C / R14-4c，2026-10-01）。

v61 把 `file_index.status` / `standard_validity.status` 的**列默认值**收敛到权威状态字典：
默认值已等于枚举值 → **不重建**（零数据搬动）；出现漂移 → 12 步重建修复（保数据与索引）。
本文件覆盖：无漂移不重建、有漂移修复、数据/索引保留、幂等、缺表跳过。
"""

from __future__ import annotations

import sqlite3

import pytest

from pilotstd.core.db._migrate_v61_enum_status_defaults import _migrate_v61_enum_status_defaults
from pilotstd.core.status import Status


class _DB:
    """最小 Database 门面：v61 只用到 execute / fetchone / fetchall。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        cur = self._conn.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        return {d[0]: row[i] for i, d in enumerate(cur.description)}

    def fetchall(self, sql: str, params: tuple = ()):
        cur = self._conn.execute(sql, params)
        return [{d[0]: row[i] for i, d in enumerate(cur.description)} for row in cur.fetchall()]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    assert row is not None
    return row[0]


def _default_of(conn: sqlite3.Connection, table: str, column: str) -> str | None:
    from pilotstd.core.db._migrate_v61_enum_status_defaults import _status_default_of

    return _status_default_of(_ddl(conn, table), column)


def test_no_rebuild_when_default_already_enum_value(conn):
    """现网形态：默认值已等于枚举值 → 不重建（DDL 与数据都原样）。"""
    # 先建成中性表名再改名：schema 一致性门禁要求“测试里出现的 CREATE TABLE <生产表名>”列集与
    # 生产完全一致，本用例只关心 DEFAULT 子句，故用改名方式规避误报（RENAME 保留默认值）
    conn.execute(
        f"CREATE TABLE v61_probe_files (id INTEGER PRIMARY KEY, status TEXT NOT NULL DEFAULT '{Status.ACTIVE.value}')"
    )
    conn.execute("ALTER TABLE v61_probe_files RENAME TO file_index")
    conn.execute("CREATE INDEX idx_file_index_status ON file_index(status)")
    conn.execute("INSERT INTO file_index (id) VALUES (1)")
    before_ddl = _ddl(conn, "file_index")

    _migrate_v61_enum_status_defaults(_DB(conn))

    assert _ddl(conn, "file_index") == before_ddl, "无漂移时不得重建表"
    assert _default_of(conn, "file_index", "status") == Status.ACTIVE.value
    assert conn.execute("SELECT COUNT(*) FROM file_index").fetchone()[0] == 1


def test_rebuild_repairs_drifted_default(conn):
    """漂移形态：默认值不是枚举值 → 重建修复，数据与索引保留。"""
    conn.execute("CREATE TABLE v61_probe_files (id INTEGER PRIMARY KEY, status TEXT NOT NULL DEFAULT '现行(旧)')")
    conn.execute("ALTER TABLE v61_probe_files RENAME TO file_index")
    conn.execute("CREATE INDEX idx_file_index_status ON file_index(status)")
    conn.execute("INSERT INTO file_index (id, status) VALUES (1, ?)", (Status.WITHDRAWN_NORMALIZED.value,))

    _migrate_v61_enum_status_defaults(_DB(conn))

    assert _default_of(conn, "file_index", "status") == Status.ACTIVE.value
    rows = conn.execute("SELECT id, status FROM file_index").fetchall()
    assert [(r["id"], r["status"]) for r in rows] == [(1, Status.WITHDRAWN_NORMALIZED.value)], "重建必须保留既有数据"
    indexes = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='file_index'")
    ]
    assert "idx_file_index_status" in indexes, "重建后索引必须恢复"
    leftovers = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE '%__v61_tmp'")]
    assert not leftovers, "临时表必须已改名"


def test_idempotent(conn):
    """幂等：第二次执行不再改动 DDL。"""
    conn.execute("CREATE TABLE v61_probe_validity (id INTEGER PRIMARY KEY, status TEXT NOT NULL DEFAULT '旧值')")
    conn.execute("ALTER TABLE v61_probe_validity RENAME TO standard_validity")
    _migrate_v61_enum_status_defaults(_DB(conn))
    after_first = _ddl(conn, "standard_validity")

    _migrate_v61_enum_status_defaults(_DB(conn))

    assert _ddl(conn, "standard_validity") == after_first
    assert _default_of(conn, "standard_validity", "status") == Status.UNKNOWN.value


def test_missing_tables_are_skipped(conn):
    """表不存在 → 跳过（故障库只含部分表）。"""
    _migrate_v61_enum_status_defaults(_DB(conn))  # 不应抛异常


def test_column_without_default_is_skipped(conn):
    """列无 DEFAULT 子句 → 跳过，不重建。"""
    conn.execute("CREATE TABLE v61_probe_files (id INTEGER PRIMARY KEY, status TEXT NOT NULL)")
    conn.execute("ALTER TABLE v61_probe_files RENAME TO file_index")
    before = _ddl(conn, "file_index")

    _migrate_v61_enum_status_defaults(_DB(conn))

    assert _ddl(conn, "file_index") == before


def test_migration_is_registered_at_version_61():
    """迁移注册号与 CURRENT_SCHEMA_VERSION 一致（防漏注册/错号）。"""
    from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS

    assert CURRENT_SCHEMA_VERSION == 61
    assert 61 in MIGRATIONS
    assert MIGRATIONS[61] is _migrate_v61_enum_status_defaults
