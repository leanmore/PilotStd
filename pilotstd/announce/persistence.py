# pilotstd/announce/persistence.py
"""Fetch checkpoint, failure log, and async task persistence.

Compatible with both Database (fetchone/execute returning dicts) and
raw sqlite3 (cursor-based). Rows are accessed by column name in both.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class AnnouncePersistence:
    """Checkpoint, failure log, and async task state SQL persistence."""

    def __init__(self, db: Any):
        self._db = db

    def _query_one(self, sql: str, params: tuple = ()) -> Any:
        """Execute SELECT and return a single row (dict or sqlite3.Row)."""
        if hasattr(self._db, "fetchone"):
            return self._db.fetchone(sql, params)
        cur = self._db.execute(sql, params)
        return cur.fetchone()

    def _exec(self, sql: str, params: tuple = ()) -> None:
        """Execute DML (INSERT/UPDATE/DELETE), dual-backend compat."""
        if hasattr(self._db, "fetchone"):
            self._db.execute(sql, params)
        else:
            self._db.execute(sql, params)

    # -- checkpoint -------------------------------------------------

    def get_checkpoint(self, source_site: str) -> str | None:
        """Return last_notice_date for source_site, or None if not found."""
        row = self._query_one(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?",
            (source_site,),
        )
        if row is None:
            return None
        return row["last_notice_date"] or None

    def write_checkpoint(self, source_site: str, last_notice_date: str) -> None:
        """Write checkpoint with anti-regression guard (older dates ignored)."""
        if not last_notice_date:
            return
        current = self._query_one(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?",
            (source_site,),
        )
        if current and current["last_notice_date"] >= last_notice_date:
            return
        now = datetime.now().isoformat()
        self._exec(
            "INSERT OR REPLACE INTO fetch_checkpoint "
            "(source_site, last_fetched_at, last_notice_date) VALUES (?, ?, ?)",
            (source_site, now, last_notice_date),
        )

    # -- failure log ------------------------------------------------

    def record_failure(self, source_site: str, error_msg: str) -> None:
        """Record a fetch failure to fetch_failures table."""
        now = datetime.now().isoformat()
        self._exec(
            "INSERT INTO fetch_failures (task_type, source_site, since_date, error_message) "
            "VALUES (?, ?, ?, ?)",
            ("scheduled", source_site, "", error_msg),
        )

    # -- async task ------------------------------------------------

    def create_task(self, task_id: str) -> None:
        """Insert a new fetch_task row with status='pending'."""
        now = datetime.now().isoformat()
        self._exec(
            "INSERT INTO fetch_task (id, task_type, status, progress, created_at, updated_at) "
            "VALUES (?, 'announcement', 'pending', 0, ?, ?)",
            (task_id, now, now),
        )

    def update_task(self, task_id: str, status: str, progress: int,
                    error_msg: str = "") -> None:
        """Update fetch_task status and progress, optionally setting error_msg."""
        now = datetime.now().isoformat()
        if error_msg:
            self._exec(
                "UPDATE fetch_task SET status=?, progress=?, error_msg=?, updated_at=? "
                "WHERE id=?",
                (status, progress, error_msg, now, task_id),
            )
        else:
            self._exec(
                "UPDATE fetch_task SET status=?, progress=?, updated_at=? WHERE id=?",
                (status, progress, now, task_id),
            )
