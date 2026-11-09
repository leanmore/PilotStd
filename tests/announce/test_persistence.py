"""AnnouncePersistence 测试 — 用 sqlite3 内存库做真实 SQL 验证。"""
from __future__ import annotations

import sqlite3

import pytest

from pilotstd.announce.persistence import AnnouncePersistence


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE fetch_checkpoint (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_site TEXT NOT NULL UNIQUE,
            last_fetched_at TEXT NOT NULL DEFAULT '',
            last_notice_date TEXT NOT NULL DEFAULT '',
            since_date_override TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE fetch_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            source_site TEXT NOT NULL,
            since_date TEXT NOT NULL,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TEXT,
            resolved BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE fetch_task (
            id TEXT PRIMARY KEY,
            task_type TEXT,
            status TEXT,
            progress INTEGER,
            result_data TEXT,
            error_msg TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    return conn


@pytest.fixture
def persistence(db):
    return AnnouncePersistence(db)


class TestCheckpoint:
    def test_get_checkpoint_exists(self, persistence, db):
        db.execute(
            "INSERT INTO fetch_checkpoint (source_site, last_notice_date) VALUES (?, ?)",
            ("samr_gb", "2024-06-01"),
        )
        db.commit()
        assert persistence.get_checkpoint("samr_gb") == "2024-06-01"

    def test_get_checkpoint_not_exists(self, persistence):
        assert persistence.get_checkpoint("samr_xx") is None

    def test_write_checkpoint_newer_date_updates(self, persistence, db):
        db.execute(
            "INSERT INTO fetch_checkpoint (source_site, last_notice_date) VALUES (?, ?)",
            ("samr_gb", "2024-06-01"),
        )
        db.commit()
        persistence.write_checkpoint("samr_gb", "2024-06-15")
        row = db.execute(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?",
            ("samr_gb",),
        ).fetchone()
        assert row["last_notice_date"] == "2024-06-15"

    def test_write_checkpoint_older_date_no_update(self, persistence, db):
        db.execute(
            "INSERT INTO fetch_checkpoint (source_site, last_notice_date) VALUES (?, ?)",
            ("samr_gb", "2024-06-15"),
        )
        db.commit()
        persistence.write_checkpoint("samr_gb", "2024-06-01")
        row = db.execute(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?",
            ("samr_gb",),
        ).fetchone()
        assert row["last_notice_date"] == "2024-06-15"


class TestFailureLog:
    def test_record_failure(self, persistence, db):
        persistence.record_failure("samr_gb", "网络超时")
        row = db.execute(
            "SELECT * FROM fetch_failures WHERE source_site=?",
            ("samr_gb",),
        ).fetchone()
        assert row is not None
        assert row["error_message"] == "网络超时"

    def test_list_failures_newest_first_and_filter_unresolved(self, persistence, db):
        persistence.record_failure("samr_gb", "第一次失败")
        persistence.record_failure("samr_hb", "第二次失败")
        db.execute("UPDATE fetch_failures SET resolved=1 WHERE source_site='samr_gb'")
        db.commit()

        all_items = persistence.list_failures(limit=10, unresolved_only=False)
        assert [r["source_site"] for r in all_items][0] == "samr_hb"
        assert len(all_items) == 2

        unresolved = persistence.list_failures(limit=10, unresolved_only=True)
        assert len(unresolved) == 1
        assert unresolved[0]["source_site"] == "samr_hb"

        counts = persistence.failure_counts()
        assert counts == {"total": 2, "unresolved": 1}

    def test_resolve_failure_marks_resolved(self, persistence, db):
        persistence.record_failure("samr_db", "超时")
        row = db.execute("SELECT id FROM fetch_failures").fetchone()
        assert persistence.resolve_failure(row["id"]) == 1
        assert persistence.failure_counts()["unresolved"] == 0
        assert persistence.list_failures(limit=10, unresolved_only=True) == []

    def test_successful_site_resolves_only_its_failures(self, persistence, db):
        persistence.record_failure("samr_gb", "旧失败")
        persistence.record_failure("samr_hb", "另一个站")
        assert persistence.resolve_site_failures("samr_gb") == 1
        counts = persistence.failure_counts()
        assert counts == {"total": 2, "unresolved": 1}
        unresolved = persistence.list_failures(limit=10, unresolved_only=True)
        assert [r["source_site"] for r in unresolved] == ["samr_hb"]


class TestTask:
    def test_create_and_update_task(self, persistence, db):
        persistence.create_task("task_001")
        row = db.execute(
            "SELECT * FROM fetch_task WHERE id=?", ("task_001",)
        ).fetchone()
        assert row["status"] == "pending"
        assert row["progress"] == 0

        persistence.update_task("task_001", "success", 100)
        row = db.execute(
            "SELECT * FROM fetch_task WHERE id=?", ("task_001",)
        ).fetchone()
        assert row["status"] == "success"
        assert row["progress"] == 100

    def test_update_task_with_error_msg(self, persistence, db):
        persistence.create_task("task_002")
        persistence.update_task("task_002", "failed", 50, "引擎崩溃")
        row = db.execute(
            "SELECT * FROM fetch_task WHERE id=?", ("task_002",)
        ).fetchone()
        assert row["status"] == "failed"
        assert row["progress"] == 50
        assert row["error_msg"] == "引擎崩溃"
