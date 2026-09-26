# tests/test_migrate_v60.py — v60 删除 user_favorites 归档重试死列测试
"""验证 v60 迁移（技术债 #16 残留清理）：

- 列存在库：两列被删除，原有数据行与其余列值不变，无关索引保留
- 只存在一列：只删存在的那一列
- 缺列库：安全跳过，不抛异常
- 表不存在：安全跳过，不抛异常
- 幂等：重复执行零副作用
- 降级：DROP 不被支持（旧 SQLite）时告警而非抛异常（两列零读取方，不该阻断启动）
- 新库跑完整迁移链后两列不存在（v36/v52/v59 补列 → v60 删列，收敛到"无此列"）
- 注册状态：MIGRATIONS[60] 已注册且 CURRENT_SCHEMA_VERSION 不低于 60
"""

import sqlite3

import pytest

from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS
from pilotstd.core.db._migrate_v60_drop_favorite_retry_columns import (
    _migrate_v60_drop_favorite_retry_columns,
)

_DROP_COLUMNS = ("archive_retry_count", "last_archive_attempt")

# v59 时点的 user_favorites 生产结构（两列尚在；v60 之后迁移链最终形态不再含它们）
_V59_DDL = (
    "CREATE TABLE user_favorites (id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "user_id INTEGER NOT NULL,record_id INTEGER NOT NULL,status TEXT DEFAULT 'pending',"
    "local_path TEXT,error_message TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,"
    "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, publish_date TEXT,"
    " standard_type TEXT NOT NULL DEFAULT 'Unknown', standard_number TEXT,"
    "FOREIGN KEY (user_id) REFERENCES users(id),"
    "FOREIGN KEY (record_id) REFERENCES announcement_record(id),"
    "UNIQUE(user_id, record_id))"
)

# 被删两列由等价的 ALTER 追加：它们是 v60 之前的历史形态，写进 CREATE TABLE 会被
# check_schema_consistency 误判为"测试表有生产表无"（EXTRA），构造结果与 v59 完全一致。
_RETRY_DDL = (
    "ALTER TABLE user_favorites ADD COLUMN last_archive_attempt TEXT",
    "ALTER TABLE user_favorites ADD COLUMN archive_retry_count INTEGER DEFAULT 0",
)

# 基础列在任何被删列存在与否时都在；两列的取值单独 UPDATE（缺列库不能出现在 INSERT 列表里）
_INSERT = (
    "INSERT INTO user_favorites (user_id, record_id, status, local_path, error_message,"
    " publish_date, standard_number, standard_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
_ROW = (1, 100, "pending", "/lib/a.pdf", None, "2026-01-01", "GB/T 1-2020", "NationalStd")
_RETRY_VALUES = {"last_archive_attempt": "'2026-01-02 03:04:05'", "archive_retry_count": "7"}


class _FakeDb:
    """把 sqlite3.Connection 适配为迁移函数所需的 Database 接口。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchall()


# v36/v52/v59 建在 user_favorites 上的三个索引（生产实况）；删列不得牵连它们
_INDEX_DDL = (
    "CREATE INDEX idx_user_favorites_user_id ON user_favorites(user_id)",
    "CREATE INDEX idx_user_favorites_status ON user_favorites(status)",
    "CREATE INDEX idx_user_favorites_record_id ON user_favorites(record_id)",
)


def _db_with(columns: tuple[str, ...] = _DROP_COLUMNS, with_row: bool = True) -> _FakeDb:
    """构造指定列存在性的 user_favorites 库（v59 时点结构：基础 DDL + 两列 ALTER + 三索引）。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_V59_DDL)
    for ddl in _RETRY_DDL:
        conn.execute(ddl)
    for ddl in _INDEX_DDL:
        conn.execute(ddl)
    for col in _DROP_COLUMNS:
        if col not in columns:
            conn.execute(f"ALTER TABLE user_favorites DROP COLUMN {col}")  # noqa: S608 — 列名来自本文件常量
    if with_row:
        conn.execute(_INSERT, _ROW)
        for col in columns:
            conn.execute(
                f"UPDATE user_favorites SET {col} = {_RETRY_VALUES[col]} WHERE user_id = 1"  # noqa: S608 — 常量
            )
    return _FakeDb(conn)


def _cols(db: _FakeDb) -> list[str]:
    return [r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")]


class TestMigrateV60:
    """v60 迁移行为验证。"""

    def test_drops_both_columns_and_keeps_data(self):
        """列存在库：两列被删除，数据行与其余列值原样保留，三个无关索引不被牵连。"""
        db = _db_with()
        before = dict(db.fetchone("SELECT * FROM user_favorites WHERE user_id=1"))

        _migrate_v60_drop_favorite_retry_columns(db)

        cols = _cols(db)
        for col in _DROP_COLUMNS:
            assert col not in cols, f"{col} 应被删除，实际列: {cols}"
        after = dict(db.fetchone("SELECT * FROM user_favorites WHERE user_id=1"))
        expected = {k: v for k, v in before.items() if k not in _DROP_COLUMNS}
        assert after == expected, "被删列之外的列值不得改动"
        indexes = {r["name"] for r in db.fetchall("PRAGMA index_list(user_favorites)")}
        for name in ("idx_user_favorites_user_id", "idx_user_favorites_status", "idx_user_favorites_record_id"):
            assert name in indexes, f"无关索引 {name} 不得丢失，实际: {sorted(indexes)}"

    def test_only_present_column_is_dropped(self):
        """只有 archive_retry_count 时，只删这一列，缺失列不报错。"""
        db = _db_with(columns=("archive_retry_count",))

        _migrate_v60_drop_favorite_retry_columns(db)

        assert _cols(db).count("archive_retry_count") == 0
        assert db.fetchone("SELECT standard_number FROM user_favorites WHERE user_id=1")["standard_number"] == (
            "GB/T 1-2020"
        )

    def test_missing_columns_is_noop(self):
        """缺列库：安全跳过，不抛异常，数据不受影响。"""
        db = _db_with(columns=())

        _migrate_v60_drop_favorite_retry_columns(db)

        assert set(_cols(db)).isdisjoint(_DROP_COLUMNS)
        assert db.fetchone("SELECT COUNT(*) AS c FROM user_favorites")["c"] == 1

    def test_missing_table_is_noop(self):
        """表不存在：安全跳过，不抛异常。"""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db = _FakeDb(conn)

        _migrate_v60_drop_favorite_retry_columns(db)

        tables = {r["name"] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "user_favorites" not in tables, "迁移不得凭空建表"

    def test_idempotent(self):
        """重复执行零副作用。"""
        db = _db_with()

        _migrate_v60_drop_favorite_retry_columns(db)
        first = _cols(db)
        _migrate_v60_drop_favorite_retry_columns(db)

        assert _cols(db) == first
        assert db.fetchone("SELECT COUNT(*) AS c FROM user_favorites")["c"] == 1

    def test_degraded_when_drop_unsupported(self, caplog):
        """DROP 失败（旧 SQLite / 被约束引用）时告警降级，不抛异常阻断启动。"""

        class _RefusingDb:
            """表与列都在，但任何 ALTER ... DROP COLUMN 都失败。"""

            def __init__(self) -> None:
                self.conn = sqlite3.connect(":memory:")
                self.conn.row_factory = sqlite3.Row
                self.conn.execute(_V59_DDL)
                for ddl in _RETRY_DDL:
                    self.conn.execute(ddl)

            def fetchone(self, sql: str, params: tuple = ()):
                return self.conn.execute(sql, params).fetchone()

            def fetchall(self, sql: str, params: tuple = ()):
                return self.conn.execute(sql, params).fetchall()

            def execute(self, sql: str, params: tuple = ()):
                if "DROP COLUMN" in sql:
                    raise sqlite3.OperationalError("near \"DROP\": syntax error")
                return self.conn.execute(sql, params)

        db = _RefusingDb()
        with caplog.at_level("WARNING", logger="pilotstd.db.migrate.v60"):
            _migrate_v60_drop_favorite_retry_columns(db)  # 不抛异常即通过

        assert "保留该列" in caplog.text, "降级路径必须留下可观测告警"

    def test_registered_and_version_bumped(self):
        """迁移已注册到 MIGRATIONS，且当前期望版本号不低于 60。

        用 >= 而非 ==：版本号随每次新增迁移递增，钉死具体值会让后续每个迁移
        都要回来改这条断言。
        """
        assert 60 in MIGRATIONS, "MIGRATIONS 注册表缺少 v60"
        assert CURRENT_SCHEMA_VERSION >= 60, "CURRENT_SCHEMA_VERSION 应不低于 60"

    def test_fresh_database_full_chain_has_no_dead_columns(self, tmp_path):
        """新库跑完整迁移链（v36/v52/v59 补列 → v60 删列）后两列不存在。"""
        from pilotstd.core.db import Database

        path = str(tmp_path / "fresh.db")
        db = Database(path)
        try:
            assert db.schema_version == CURRENT_SCHEMA_VERSION
            cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")}
        finally:
            db.close()

        assert cols.isdisjoint(_DROP_COLUMNS), f"完整迁移链后仍存在死列: {sorted(cols & set(_DROP_COLUMNS))}"
        assert {"publish_date", "standard_type", "standard_number"} <= cols, "无关列不得被误删"


@pytest.mark.parametrize("column", _DROP_COLUMNS)
def test_no_production_reader_remains(column: str):
    """回归护栏：生产代码（pilotstd/ 与 docker/）不得再引用被删列。

    两列的死列属性是本次删除的前提；一旦有人重新读它们，SQL 会直接
    `no such column` 报错，故在此把"零读取方"钉成断言。迁移文件自身
    （P-106 源码不可变的历史迁移）天然仍在引用，故排除。
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    hits: list[str] = []
    for base in (root / "pilotstd", root / "docker"):
        for path in base.rglob("*.py"):
            if path.name.startswith("_migrate_") or path.name == "migrations.py":
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(rf"\b{column}\b", text):
                hits.append(str(path.relative_to(root)))
    assert hits == [], f"生产代码仍在引用 {column}: {hits}"
