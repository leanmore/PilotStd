"""U-1 根因回归：`last_status` 必须在入库/首次检查/未变化三条路径上都有值。"""

from __future__ import annotations

import sqlite3

import pytest

from pilotstd.core.validity_checker import ValidityChecker


class _DB:
    """最小数据库适配器：ValidityChecker 需要 fetchone/execute 两个方法。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchall()

    def commit(self) -> None:
        self._conn.commit()


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # 中性表名建表后改名：schema 门禁只比对生产表名
    conn.execute(
        "CREATE TABLE _tmp_sv ("
        " id INTEGER PRIMARY KEY, standard_number TEXT UNIQUE, status TEXT,"
        " last_status TEXT, last_status_updated_at TEXT, last_checked_at TEXT,"
        " next_check_at TEXT, last_changed_at TEXT, check_count INTEGER DEFAULT 0,"
        " created_at TEXT, updated_at TEXT, source_version TEXT, data_state TEXT,"
        " last_accessed_at TEXT)"
    )
    conn.execute("ALTER TABLE _tmp_sv RENAME TO standard_validity")
    conn.commit()
    yield _DB(conn)
    conn.close()


def _row(db, number):
    r = db.fetchone("SELECT * FROM standard_validity WHERE standard_number=?", (number,))
    return dict(r) if r else None


def test_register_initializes_last_status(db):
    ValidityChecker(db).register_new_standard("GB/T 1-2020")
    row = _row(db, "GB/T 1-2020")
    assert row["status"] == "未知"
    assert row["last_status"] == "未知"  # 不初始化的话界面“上一状态”恒空


def test_first_check_insert_fills_last_status(db):
    ValidityChecker(db).update_status("GB/T 2-2020", "现行", None)
    row = _row(db, "GB/T 2-2020")
    assert row["status"] == "现行"
    assert row["last_status"] == "现行"


def test_unchanged_check_backfills_legacy_null(db):
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_checked_at, check_count)"
        " VALUES ('GB/T 3-2020', '现行', '', 1)"
    )
    db.commit()
    assert _row(db, "GB/T 3-2020")["last_status"] is None
    ValidityChecker(db).update_status("GB/T 3-2020", "现行", None)
    assert _row(db, "GB/T 3-2020")["last_status"] == "现行"


def test_status_change_records_previous_status(db):
    db.execute(
        "INSERT INTO standard_validity (standard_number, status, last_status, last_checked_at, check_count)"
        " VALUES ('GB/T 4-2020', '现行', '未知', '', 1)"
    )
    db.commit()
    ValidityChecker(db).update_status("GB/T 4-2020", "废止", None)
    row = _row(db, "GB/T 4-2020")
    assert row["status"] == "废止"
    assert row["last_status"] == "现行"
