# tests/test_migrate_v44_favorite_downloads_data.py — v44 归档状态搬迁
"""验证 v44：user_favorites 的归档状态行搬到 favorite_downloads，原表状态重置。

覆盖：
- 5 种归档状态（downloading/archiving/done/failed/abandoned）全部搬迁；
- 原表这 5 行状态重置为 pending（回归纯收藏语义）；
- 非归档状态行、record_id 为空的行不受影响。
"""

import sqlite3

from pilotstd.core.db._migrate_v44 import _migrate_v44_favorite_downloads

_ARCHIVE_STATUSES = ("downloading", "archiving", "done", "failed", "abandoned")


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
    """造 user_favorites（含归档状态列）+ announcement_record 最小表。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE tmp_announcement_record (id INTEGER PRIMARY KEY, standard_number TEXT)"
    )
    conn.execute("ALTER TABLE tmp_announcement_record RENAME TO announcement_record")
    conn.execute(
        """CREATE TABLE tmp_user_favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            record_id INTEGER,
            status TEXT DEFAULT 'pending',
            local_path TEXT,
            error_message TEXT,
            archive_retry_count INTEGER DEFAULT 0,
            last_archive_attempt TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute("ALTER TABLE tmp_user_favorites RENAME TO user_favorites")
    for i in range(1, 6):
        conn.execute("INSERT INTO announcement_record (id, standard_number) VALUES (?, ?)", (i, f"GB {i}"))
        conn.execute(
            "INSERT INTO user_favorites (id, record_id, status, local_path, error_message)"
            " VALUES (?, ?, ?, ?, ?)",
            (i, i, _ARCHIVE_STATUSES[i - 1], f"/x/{i}.pdf", ""),
        )
    # 非归档状态：不应被搬走
    conn.execute(
        "INSERT INTO user_favorites (id, record_id, status) VALUES (10, 1, 'pending')"
    )
    # 归档状态但 record_id 为空：不迁、不改
    conn.execute(
        "INSERT INTO user_favorites (id, record_id, status) VALUES (11, NULL, 'done')"
    )
    return _FakeDb(conn)


def test_migrates_all_archive_status_rows() -> None:
    """5 种归档状态 → favorite_downloads 各 1 行。"""
    db = _prepare_db()
    _migrate_v44_favorite_downloads(db)

    rows = db.fetchall("SELECT favorite_id, status, local_path FROM favorite_downloads ORDER BY favorite_id")
    assert [r["favorite_id"] for r in rows] == [1, 2, 3, 4, 5]
    assert [r["status"] for r in rows] == list(_ARCHIVE_STATUSES)
    assert rows[0]["local_path"] == "/x/1.pdf"


def test_resets_archive_status_on_user_favorites() -> None:
    """原表 5 行状态重置为 pending。"""
    db = _prepare_db()
    _migrate_v44_favorite_downloads(db)

    rows = db.fetchall("SELECT id, status FROM user_favorites WHERE id <= 5 ORDER BY id")
    assert [r["status"] for r in rows] == ["pending"] * 5


def test_leaves_non_archive_and_null_record_rows_untouched() -> None:
    """非归档状态、record_id 为空的行：既不迁移也不改状态。"""
    db = _prepare_db()
    _migrate_v44_favorite_downloads(db)

    assert db.fetchone("SELECT COUNT(*) AS c FROM favorite_downloads")["c"] == 5
    pending_row = db.fetchone("SELECT status FROM user_favorites WHERE id=10")
    assert pending_row["status"] == "pending"
    null_row = db.fetchone("SELECT status FROM user_favorites WHERE id=11")
    assert null_row["status"] == "done"


def test_skips_data_migration_when_archive_columns_missing(caplog) -> None:
    """缺归档列（v36 未跑）→ 跳过数据搬迁，favorite_downloads 保持空。

    注意（既有行为，非本测试期望值）：清理语句**无条件执行**，所以状态仍会被重置为
    pending —— 即「没搬走却改了原表状态」。此处如实断言，供后续若改判时作回归锚点。
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE tmp_user_favorites ("
        " id INTEGER PRIMARY KEY, record_id INTEGER, status TEXT, updated_at TEXT)"
    )
    conn.execute("ALTER TABLE tmp_user_favorites RENAME TO user_favorites")
    conn.execute("INSERT INTO user_favorites (id, record_id, status) VALUES (1, 1, 'done')")
    db = _FakeDb(conn)

    _migrate_v44_favorite_downloads(db)

    assert db.fetchone("SELECT COUNT(*) AS c FROM favorite_downloads")["c"] == 0
    assert db.fetchone("SELECT status FROM user_favorites WHERE id=1")["status"] == "pending"
