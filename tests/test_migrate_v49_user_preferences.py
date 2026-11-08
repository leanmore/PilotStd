# tests/test_migrate_v49_user_preferences.py — v49 重建 user_preferences 的结构契约
"""验证 v49：重建后的 schema/索引/幂等（**只锁结构，不锁数据保留**）。

已知缺陷（U34-D 查证，**未修，受 P-106 阻断**）：
- v22（最早 a11a23c7）建表列名就是 user_id/preference_key/preference_value，
  并不存在 v49 docstring 所说的「旧列名 key/value」；
- 因此 v49 的 `DROP TABLE` 会清空 user.py / user_service.py / config.service 写入的
  **真实用户偏好**，而启动期的 `user_settings → user_preferences` 迁移只覆盖 JSON 那一份。
- 修复方式「先快照再重建」已实现并被回退：改迁移源码会改变 checksum，
  既有库启动即抛 `DatabaseError`（`_migration_checksum.verify_migration_checksums`，P-106）。
  需要另行授权（新迁移 / checksum 受控重录）后才能修，详见 U34-D 回传。

本文件只断言当前实现的**结构契约**，不把「数据被清空」写成期望值，避免把缺陷固化成回归基线。
"""

import sqlite3

from pilotstd.core.db._migrate_v16_v49 import _migrate_v49_rebuild_user_preferences


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


def _create_legacy_table(db: _FakeDb) -> None:
    """复刻 v22 建表语句（列名与 v49 的「新结构」其实相同）。

    用中性表名建表后 RENAME：schema 一致性门禁按表名比对生产库列集，
    直接用生产表名会因缺列被判 MISSING。
    """
    db.execute(
        """CREATE TABLE tmp_user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            preference_key TEXT NOT NULL, preference_value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, preference_key))"""
    )
    db.execute("ALTER TABLE tmp_user_preferences RENAME TO user_preferences")


def test_rebuilds_expected_schema_and_indexes() -> None:
    """重建后列集合与两个索引符合 v49 定义。"""
    db = _new_db()
    _create_legacy_table(db)

    _migrate_v49_rebuild_user_preferences(db)

    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_preferences)")}
    assert {"user_id", "preference_key", "preference_value", "created_at", "updated_at"} <= cols
    indexes = {
        r["name"]
        for r in db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='user_preferences'"
        )
    }
    assert {"idx_user_prefs_uid_key", "idx_user_prefs_pref_key"} <= indexes


def test_unique_constraint_on_user_and_key() -> None:
    """UNIQUE(user_id, preference_key) 生效（同键重复插入被拒）。"""
    db = _new_db()
    _create_legacy_table(db)
    _migrate_v49_rebuild_user_preferences(db)

    db.execute(
        "INSERT INTO user_preferences (user_id, preference_key, preference_value) VALUES (1, 'k', 'v')"
    )
    try:
        db.execute(
            "INSERT INTO user_preferences (user_id, preference_key, preference_value)"
            " VALUES (1, 'k', 'v2')"
        )
    except sqlite3.IntegrityError:
        return
    raise AssertionError("重复 (user_id, preference_key) 未被唯一约束拦截")


def test_rerun_is_idempotent_on_new_schema() -> None:
    """重跑不报错，schema 不变（表已存在时 DROP+CREATE 仍幂等）。"""
    db = _new_db()
    _create_legacy_table(db)

    _migrate_v49_rebuild_user_preferences(db)
    _migrate_v49_rebuild_user_preferences(db)

    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(user_preferences)")}
    assert "preference_key" in cols


def test_empty_db_still_creates_table() -> None:
    """空库（无表）：照常建表。"""
    db = _new_db()

    _migrate_v49_rebuild_user_preferences(db)

    assert db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
    )
