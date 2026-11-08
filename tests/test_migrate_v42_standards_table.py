# tests/test_migrate_v42_standards_table.py — v42 建 standards 表与索引
"""验证 v42：空库跑迁移 → standards 表 + 3 个索引（1 个唯一 + 2 个普通）。

注：工单描述为「4 个唯一索引」，实际代码只建 3 个（idx_standards_four_elements 唯一，
另两个是普通索引）——本文件按代码事实断言，差异已在 U34-D 回传中说明。
"""

import sqlite3

from pilotstd.core.db._migrate_v16_v49 import _migrate_v42_create_standards_table


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


def test_creates_standards_table() -> None:
    """空库 → standards 表被创建。"""
    db = _new_db()
    _migrate_v42_create_standards_table(db)

    row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='standards'")
    assert row is not None


def test_creates_expected_indexes() -> None:
    """索引：四要素唯一 + 扫描状态 + 代号/名称。"""
    db = _new_db()
    _migrate_v42_create_standards_table(db)

    indexes = {
        r["name"]
        for r in db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='standards'"
        )
    }
    assert {
        "idx_standards_four_elements",
        "idx_standards_scan_status",
        "idx_standards_code_name",
    } <= indexes


def test_four_element_index_is_unique_over_four_columns() -> None:
    """四要素唯一索引必须覆盖 (sha256, code, name, size)。"""
    db = _new_db()
    _migrate_v42_create_standards_table(db)

    row = db.fetchone(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_standards_four_elements'"
    )
    assert row is not None
    sql = row["sql"] or ""
    assert "UNIQUE" in sql.upper()
    for col in ("sha256", "code", "name", "size"):
        assert col in sql


def test_scan_status_check_constraint() -> None:
    """scan_status 只允许 pending/indexed（CHECK 生效）。"""
    db = _new_db()
    _migrate_v42_create_standards_table(db)

    db.execute(
        "INSERT INTO standards (sha256, code, name, size) VALUES ('h', 'GB', 'n', 1)"
    )
    try:
        db.execute(
            "INSERT INTO standards (sha256, code, name, size, scan_status)"
            " VALUES ('h2', 'GB', 'n2', 2, 'bogus')"
        )
    except sqlite3.IntegrityError:
        return
    raise AssertionError("非法 scan_status 未被 CHECK 拦截")
