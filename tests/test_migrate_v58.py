# tests/test_migrate_v58.py — v58 幂等补建 app_preferences 表测试（N-01 修复）
"""验证 v58 迁移：

- 缺表库：创建 app_preferences 表并插入 announce_since_date 默认值
- 已建表库（模拟 v20 已执行场景）：重复执行无副作用（幂等）
- 默认行已存在：INSERT OR IGNORE 不重复插入
- 注册状态：MIGRATIONS[58] 已注册且 CURRENT_SCHEMA_VERSION == 58
"""

import sqlite3

from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS
from pilotstd.core.db._migrate_v58_ensure_app_preferences import (
    _migrate_v58_ensure_app_preferences,
)


class _FakeDb:
    """将 sqlite3.Connection 适配为迁移函数所需的 Database 接口（execute/fetchone/fetchall）。"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params).fetchall()


def _new_db() -> _FakeDb:
    """创建空内存库（无 app_preferences 表），启用 Row 工厂以支持按列名索引。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return _FakeDb(conn)


class TestMigrateV58:
    """v58 迁移行为验证。"""

    def test_creates_table_and_default_row(self):
        """缺表库：建表 + 插入 announce_since_date 默认值。"""
        db = _new_db()
        _migrate_v58_ensure_app_preferences(db)

        table = db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='app_preferences'"
        )
        assert table is not None, "app_preferences 表未创建"

        row = db.fetchone("SELECT value FROM app_preferences WHERE key='announce_since_date'")
        assert row is not None, "announce_since_date 默认行未插入"
        assert row["value"] == ""

    def test_table_schema_matches_v20_definition(self):
        """表结构与 v20 迁移定义一致（key/value/updated_at）。"""
        db = _new_db()
        _migrate_v58_ensure_app_preferences(db)

        cols = {r["name"] for r in db.fetchall("PRAGMA table_info(app_preferences)")}
        assert cols == {"key", "value", "updated_at"}
        pk = db.fetchone("PRAGMA table_info(app_preferences)")
        assert pk["pk"] == 1 and pk["name"] == "key", "key 应为主键"

    def test_idempotent_on_existing_table(self):
        """已建表且含数据：重复执行不报错、不覆盖、不重复插行（幂等）。"""
        db = _new_db()
        _migrate_v58_ensure_app_preferences(db)
        db.execute(
            "UPDATE app_preferences SET value='2026-08-01' WHERE key='announce_since_date'"
        )

        _migrate_v58_ensure_app_preferences(db)  # 第二次执行

        row = db.fetchone("SELECT value FROM app_preferences WHERE key='announce_since_date'")
        assert row["value"] == "2026-08-01", "幂等执行不应覆盖既有值"
        cnt = db.fetchone("SELECT COUNT(*) AS cnt FROM app_preferences")
        assert cnt["cnt"] == 1, "INSERT OR IGNORE 不应重复插行"

    def test_registered_and_version_bumped(self):
        """迁移已注册到 MIGRATIONS，且当前期望版本号为 58。"""
        assert 58 in MIGRATIONS, "MIGRATIONS 注册表缺少 v58"
        assert CURRENT_SCHEMA_VERSION == 58, "CURRENT_SCHEMA_VERSION 应为 58"
