# tests/test_migrate_v76_validity_check_log.py — v76 建时效性检查病历表
"""验证 v76：validity_check_log 表 + 列集合 + 两个查询索引。"""

import sqlite3

from pilotstd.core.db._migrate_v76_validity_check_log import _migrate_v76_validity_check_log

_EXPECTED_COLUMNS = {
    "id",
    "standard_number",
    "checked_at",
    "evidence",
    "status",
    "previous_status",
    "found_name",
    "source_site",
    "match_status",
    "ok",
    "error",
    "result_json",
}


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


def test_creates_log_table_with_full_schema() -> None:
    """空库 → 表存在，12 列齐全。"""
    db = _new_db()
    _migrate_v76_validity_check_log(db)

    assert db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='validity_check_log'"
    )
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(validity_check_log)")}
    assert cols == _EXPECTED_COLUMNS


def test_defaults_match_contract() -> None:
    """最小插入：evidence/status/found_name/match_status/result_json 默认空串，ok 默认 1。"""
    db = _new_db()
    _migrate_v76_validity_check_log(db)
    db.execute(
        "INSERT INTO validity_check_log (standard_number, checked_at) VALUES ('GB 1', 't')"
    )

    row = db.fetchone("SELECT * FROM validity_check_log")
    assert row["evidence"] == ""
    assert row["status"] == ""
    assert row["found_name"] == ""
    assert row["match_status"] == ""
    assert row["result_json"] == ""
    assert row["ok"] == 1
    assert row["previous_status"] is None


def test_creates_two_query_indexes() -> None:
    """standard_number+checked_at 与 checked_at 两个索引。"""
    db = _new_db()
    _migrate_v76_validity_check_log(db)

    indexes = {
        r["name"]
        for r in db.fetchall(
            "SELECT name FROM sqlite_master"
            " WHERE type='index' AND tbl_name='validity_check_log'"
        )
    }
    assert {"idx_validity_check_std", "idx_validity_check_time"} <= indexes


def test_rerun_is_idempotent() -> None:
    """重跑不报错（IF NOT EXISTS）。"""
    db = _new_db()
    _migrate_v76_validity_check_log(db)
    _migrate_v76_validity_check_log(db)
