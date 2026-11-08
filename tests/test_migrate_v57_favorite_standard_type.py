# tests/test_migrate_v57_favorite_standard_type.py — v57 收藏分类回填
"""验证 v57：4 表补 standard_type + 精确映射回填 + dry-run 预览。

覆盖：
- announcement_record 按 source_site 精确映射（gb/hb/db）；
- 映射不到的来源保持 Unknown（不得猜）；
- user_favorites 经 record_id 关联回填；
- 重跑幂等（第二轮不再更新）；
- MIGRATE_DRY_RUN=1 只预览、不改库（覆盖 _preview_counts 分支）。
"""

import sqlite3

from pilotstd.constants.announce_types import SOURCE_SITE_TO_STANDARD_TYPE
from pilotstd.core.db._migrate_v57 import (
    _migrate_v57_favorite_standard_type,
    _preview_counts,
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


def _new_db() -> _FakeDb:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return _FakeDb(conn)


def _prepare_db() -> _FakeDb:
    db = _new_db()
    db.execute(
        "CREATE TABLE tmp_announcement_record ("
        " id INTEGER PRIMARY KEY, standard_number TEXT, source_site TEXT,"
        " standard_type TEXT NOT NULL DEFAULT 'Unknown')"
    )
    db.execute("ALTER TABLE tmp_announcement_record RENAME TO announcement_record")
    db.execute(
        "CREATE TABLE tmp_user_favorites ("
        " id INTEGER PRIMARY KEY, record_id INTEGER,"
        " standard_type TEXT NOT NULL DEFAULT 'Unknown', status TEXT)"
    )
    db.execute("ALTER TABLE tmp_user_favorites RENAME TO user_favorites")
    for sid, number, site in (
        (1, "GB 1", "announcement_gb"),
        (2, "HB 2", "announcement_hb"),
        (3, "DB 3", "announcement_db"),
        (4, "XX 9", "announcement_unknown_source"),
    ):
        db.execute(
            "INSERT INTO announcement_record (id, standard_number, source_site) VALUES (?, ?, ?)",
            (sid, number, site),
        )
    db.execute("INSERT INTO user_favorites (id, record_id) VALUES (1, 1)")
    return db


def test_announcement_record_backfilled_by_exact_mapping() -> None:
    """gb/hb/db 精确映射到三个枚举值；未知来源保持 Unknown。"""
    db = _prepare_db()
    _migrate_v57_favorite_standard_type(db)

    types = {
        r["id"]: r["standard_type"]
        for r in db.fetchall("SELECT id, standard_type FROM announcement_record")
    }
    assert types[1] == SOURCE_SITE_TO_STANDARD_TYPE["announcement_gb"]
    assert types[2] == SOURCE_SITE_TO_STANDARD_TYPE["announcement_hb"]
    assert types[3] == SOURCE_SITE_TO_STANDARD_TYPE["announcement_db"]
    assert types[4] == "Unknown", "映射不到的来源不得猜测"


def test_user_favorites_backfilled_from_record() -> None:
    """收藏表经 record_id 关联拿到同一类型。"""
    db = _prepare_db()
    _migrate_v57_favorite_standard_type(db)

    row = db.fetchone("SELECT standard_type FROM user_favorites WHERE id=1")
    assert row["standard_type"] == SOURCE_SITE_TO_STANDARD_TYPE["announcement_gb"]


def test_rerun_is_idempotent() -> None:
    """第二轮：类型已是具体值，不再选中、不再更新。"""
    db = _prepare_db()
    _migrate_v57_favorite_standard_type(db)
    before = db.fetchall("SELECT id, standard_type FROM announcement_record ORDER BY id")
    _migrate_v57_favorite_standard_type(db)
    after = db.fetchall("SELECT id, standard_type FROM announcement_record ORDER BY id")
    assert [dict(r) for r in before] == [dict(r) for r in after]


def test_dry_run_only_previews(monkeypatch) -> None:
    """MIGRATE_DRY_RUN=1：不补列、不回填，只产出预览计数。"""
    db = _prepare_db()
    monkeypatch.setenv("MIGRATE_DRY_RUN", "1")

    _migrate_v57_favorite_standard_type(db)

    assert db.fetchone("SELECT id, standard_type FROM announcement_record") is not None
    types = {r["standard_type"] for r in db.fetchall("SELECT standard_type FROM announcement_record")}
    assert types == {"Unknown"}, "dry-run 不得写库"
    preview = _preview_counts(db)
    assert preview[SOURCE_SITE_TO_STANDARD_TYPE["announcement_gb"]] == 1
    assert preview["Unknown"] == 1
