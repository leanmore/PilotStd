# tests/test_migrate_v66_announcement_final_name.py — v66 补列 + 从 pending_lookup 回填
"""验证 v66：
- 补 final_name 列（幂等，已有列不报错）；
- 从 pending_lookup 回填非空③值（取最新，不限 status）；
- 已有值的行不被覆盖（重跑幂等）；
- pending_lookup 无对应行时保持 NULL。
"""

import sqlite3

from pilotstd.core.db._migrate_v66_announcement_record_final_name import (
    _migrate_v66_announcement_record_final_name,
)


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


def _prepare_db() -> _FakeDb:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE tmp_announcement_record (id INTEGER PRIMARY KEY, standard_number TEXT)"
    )
    conn.execute("ALTER TABLE tmp_announcement_record RENAME TO announcement_record")
    conn.execute(
        """CREATE TABLE tmp_pending_lookup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL,
            final_name TEXT,
            status TEXT,
            created_at TEXT NOT NULL DEFAULT '2026-01-01'
        )"""
    )
    conn.execute("ALTER TABLE tmp_pending_lookup RENAME TO pending_lookup")
    conn.execute("INSERT INTO announcement_record (id, standard_number) VALUES (1, 'GB 1')")
    conn.execute("INSERT INTO announcement_record (id, standard_number) VALUES (2, 'GB 2')")
    # 同一标准两条③值：新的那条胜出
    conn.execute(
        "INSERT INTO pending_lookup (standard_number, final_name, status, created_at)"
        " VALUES ('GB 1', '旧名', 'resolved', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO pending_lookup (standard_number, final_name, status, created_at)"
        " VALUES ('GB 1', '新名', 'pending', '2026-01-01')"
    )
    return _FakeDb(conn)


def test_adds_column_and_backfills_latest_value() -> None:
    """补列 + 回填最新③值；无对应行的记录保持 NULL。"""
    db = _prepare_db()
    _migrate_v66_announcement_record_final_name(db)

    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(announcement_record)")}
    assert "final_name" in cols

    assert db.fetchone("SELECT final_name AS v FROM announcement_record WHERE id=1")["v"] == "新名"
    assert db.fetchone("SELECT final_name AS v FROM announcement_record WHERE id=2")["v"] is None


def test_does_not_overwrite_existing_value_on_rerun() -> None:
    """已有 final_name 的行不被回填覆盖（人工确认值优先）。"""
    db = _prepare_db()
    _migrate_v66_announcement_record_final_name(db)
    db.execute("UPDATE announcement_record SET final_name='人工值' WHERE id=1")

    _migrate_v66_announcement_record_final_name(db)

    assert db.fetchone("SELECT final_name AS v FROM announcement_record WHERE id=1")["v"] == "人工值"


def test_ignores_empty_pending_value() -> None:
    """pending_lookup 的 final_name 为空串 → 不回填。"""
    db = _prepare_db()
    db.execute("DELETE FROM pending_lookup WHERE standard_number='GB 2'")
    db.execute(
        "INSERT INTO pending_lookup (standard_number, final_name, status, created_at)"
        " VALUES ('GB 2', '', 'pending', '2026-02-01')"
    )

    _migrate_v66_announcement_record_final_name(db)

    assert db.fetchone("SELECT final_name AS v FROM announcement_record WHERE id=2")["v"] is None


def test_missing_tables_are_noop() -> None:
    """表缺失（极端库）：直接返回，不抛异常。"""
    conn = sqlite3.connect(":memory:")
    db = _FakeDb(conn)
    _migrate_v66_announcement_record_final_name(db)  # 不应抛
