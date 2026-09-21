# tests/test_migrate_v59.py — v59 兜底补全 user_favorites 归档重试列测试
"""验证 v59 迁移：

- 缺列库：补上 archive_retry_count / last_archive_attempt 两列
- 已有一列：只补缺的那一列（不重复 ALTER）
- 幂等：重复执行无副作用，既有数据不丢
- 修复目标：补列后收藏状态接口所用 SQL 不再报 no such column
- 注册状态：MIGRATIONS[59] 已注册且 CURRENT_SCHEMA_VERSION == 59
"""

import sqlite3

from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS
from pilotstd.core.db._migrate_v59_ensure_favorite_retry_columns import (
    _migrate_v59_ensure_favorite_retry_columns,
)

# 生产库 user_favorites 的完整结构（与迁移链最终形态一致，供 check_schema_consistency 校验；
# 由「跑完整迁移链后 dump sqlite_master」得到）
_FULL_DDL = (
    "CREATE TABLE user_favorites (id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "user_id INTEGER NOT NULL,record_id INTEGER NOT NULL,status TEXT DEFAULT 'pending',"
    "local_path TEXT,error_message TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,"
    "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, publish_date TEXT,"
    " last_archive_attempt TEXT, archive_retry_count INTEGER DEFAULT 0,"
    " standard_type TEXT NOT NULL DEFAULT 'Unknown', standard_number TEXT,"
    "FOREIGN KEY (user_id) REFERENCES users(id),"
    "FOREIGN KEY (record_id) REFERENCES announcement_record(id),"
    "UNIQUE(user_id, record_id))"
)

# 收藏状态接口实际使用的 SQL（docker/api/favorites.py:210-214），用于验证补列后不再报错
_STATUS_SQL = (
    "SELECT id, status, local_path, error_message, publish_date, archive_retry_count"
    " FROM user_favorites WHERE user_id = ? AND record_id = ?"
)


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


def _legacy_db(missing: tuple[str, ...] = ("archive_retry_count", "last_archive_attempt")) -> _FakeDb:
    """构造"缺列故障库"：先建生产全量结构，再 DROP 掉指定列（模拟 v36 补列未生效）。

    SQLite 3.35+ 支持 DROP COLUMN（项目要求 SQLite >= 3.35）。
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_FULL_DDL)
    for col in missing:
        conn.execute(f"ALTER TABLE user_favorites DROP COLUMN {col}")  # noqa: S608 — 列名来自本文件常量
    conn.execute(
        "INSERT INTO user_favorites (user_id, record_id, status, publish_date)"
        " VALUES (1, 100, 'pending', '2026-01-01')"
    )
    if "archive_retry_count" not in missing:
        conn.execute("UPDATE user_favorites SET archive_retry_count = 7 WHERE user_id = 1")
    return _FakeDb(conn)


class TestMigrateV59:
    """v59 迁移行为验证。"""

    def test_adds_missing_columns_and_fixes_status_query(self):
        """缺列库：迁移后两列存在，且状态接口 SQL 可执行（修复 500）。"""
        db = _legacy_db()
        _migrate_v59_ensure_favorite_retry_columns(db)

        cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")}
        assert {"archive_retry_count", "last_archive_attempt"} <= cols, cols

        row = db.fetchone(_STATUS_SQL, (1, 100))
        assert row is not None, "补列后状态接口 SQL 应能查到收藏行"
        assert row["archive_retry_count"] == 0, "补列默认值应为 0"

    def test_only_missing_column_is_added(self):
        """只有 last_archive_attempt 缺失时，只补这一列，已存在列的既有值不被覆盖。"""
        db = _legacy_db(missing=("last_archive_attempt",))

        _migrate_v59_ensure_favorite_retry_columns(db)

        cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_favorites)")}
        assert {"archive_retry_count", "last_archive_attempt"} <= cols
        row = db.fetchone("SELECT archive_retry_count FROM user_favorites WHERE user_id=1")
        assert row["archive_retry_count"] == 7, "已存在列不得被覆盖"

    def test_idempotent_and_keeps_data(self):
        """重复执行无副作用，既有行与发布时间不丢。"""
        db = _legacy_db()
        _migrate_v59_ensure_favorite_retry_columns(db)
        _migrate_v59_ensure_favorite_retry_columns(db)

        row = db.fetchone("SELECT status, publish_date FROM user_favorites WHERE user_id=1")
        assert row["status"] == "pending"
        assert row["publish_date"] == "2026-01-01"

    def test_registered_and_version_bumped(self):
        """迁移已注册到 MIGRATIONS，且当前期望版本号不低于 59。

        用 >= 而非 ==：版本号随每次新增迁移递增，钉死具体值会让后续每个迁移
        都要回来改这条断言。
        """
        assert 59 in MIGRATIONS, "MIGRATIONS 注册表缺少 v59"
        assert CURRENT_SCHEMA_VERSION >= 59, "CURRENT_SCHEMA_VERSION 应不低于 59"
