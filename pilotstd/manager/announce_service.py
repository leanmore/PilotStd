# pilotstd/manager/announce_service.py
# AnnounceService -- announcement check, task status, and user preferences.
# Fetch/crawl logic extracted to pilotstd.announce components.

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pilotstd.announce.crawler_service import AnnounceCrawler
from pilotstd.announce.notifier import AnnounceNotifier
from pilotstd.announce.persistence import AnnouncePersistence
from pilotstd.announce.task_runner import AnnounceTaskRunner

logger = logging.getLogger(__name__)


class AnnounceService:
    """Announcement check service -- delegates to announce subsystem."""

    def __init__(self, file_index: Any,
                 ocr_config: dict[str, Any] | None = None,
                 manager: Any = None):
        self._mgr = manager
        self._file_index = file_index
        self._ocr_config = ocr_config or {}
        self._last_check_start: str = ""

        self.persistence = AnnouncePersistence(file_index._db)
        self.crawler = AnnounceCrawler(file_index=file_index,
                                       persistence=self.persistence,
                                       ocr_config=ocr_config)
        # notifier / task_runner depend on crawler, wired after mgr is set
        self._notifier: AnnounceNotifier | None = None
        self._task_runner: AnnounceTaskRunner | None = None

    def _init_notifier(self) -> AnnounceNotifier:
        """Lazy-init the notifier, wiring mgr.notification_mgr and mgr.db."""
        if self._notifier is None:
            self._notifier = AnnounceNotifier(
                notification_mgr=self._mgr.notification_mgr if self._mgr else None,
                mgr_db=self._mgr.db if self._mgr else None,
            )
        return self._notifier

    def _init_task_runner(self) -> AnnounceTaskRunner:
        """Lazy-init the task runner, wiring persistence + crawler + notifier."""
        if self._task_runner is None:
            self._task_runner = AnnounceTaskRunner(
                persistence=self.persistence,
                crawler=self.crawler,
                notifier=self._init_notifier(),
            )
        return self._task_runner

    # -- concurrency lock --------------------------------------------

    def _acquire_manual_lock(self) -> bool:
        """Acquire exclusive manual fetch lock to prevent timer collision."""
        try:
            self._file_index._db.execute(
                "INSERT OR REPLACE INTO fetch_locks "
                "(lock_key, locked_at, locked_by) VALUES ('manual', ?, 'manual')",
                (datetime.now().isoformat(),),
            )
            return True
        except Exception:
            return False

    def _release_manual_lock(self) -> None:
        self._file_index._db.execute(
            "DELETE FROM fetch_locks WHERE lock_key='manual'"
        )

    def _is_manual_running(self) -> bool:
        row = self._file_index._db.fetchone(
            "SELECT 1 FROM fetch_locks WHERE lock_key='manual'"
        )
        return row is not None

    # -- user preferences -------------------------------------------

    def _get_user_since_date(self) -> str:
        row = self._file_index._db.fetchone(
            "SELECT value FROM app_preferences WHERE key='announce_since_date'"
        )
        return row["value"] if row and row["value"] else ""

    def _clear_user_since_date(self) -> None:
        self._file_index._db.execute(
            "UPDATE app_preferences SET value='' WHERE key='announce_since_date'"
        )

    def save_user_preference(self, key: str, value: str) -> None:
        """Persist a user preference key-value pair (upsert)."""
        self._file_index._db.execute(
            "INSERT OR REPLACE INTO app_preferences (key, value, updated_at) "
            "VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )

    # -- scheduled entry point --------------------------------------

    def check_announce_scheduled(self) -> dict[str, Any]:
        """Scheduled task: skip if manual running -> backfill -> incremental."""
        if self._is_manual_running():
            logger.info("manual fetch running, scheduled task skipped")
            return {"skipped": True, "reason": "manual_running"}

        self._last_check_start = datetime.now().isoformat()

        user_since = self._get_user_since_date()
        if user_since:
            logger.info("backfill fetch from user date: %s", user_since)
            result = self.check_announcements_filtered(since_date=user_since)
            self._clear_user_since_date()
        else:
            result = self.check_announcements()

        self._after_fetch(result, source="定时")
        return result

    # -- glue methods: delegate to crawler / task_runner ------------

    def check_announcements(self) -> dict[str, Any]:
        return self.crawler.check_all()

    def check_announcements_filtered(
        self,
        std_type: str | None = None,
        since_date: str = "",
        progress_callback: Any = None,
        types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Filtered announcement check — delegate to crawler.check_filtered."""
        return self.crawler.check_filtered(types=types, since_date=since_date)

    def trigger_fetch(self, adapter_name: str = "") -> dict[str, Any]:
        return self._init_task_runner().trigger(adapter_name)

    def _after_fetch(self, result: dict[str, Any], source: str = "") -> None:
        self._init_notifier().after_fetch(result, source)

    # -- task status queries ----------------------------------------

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Query async fetch task progress by id."""
        db = self._get_db()
        row = db.fetchone("SELECT * FROM fetch_task WHERE id=?", (task_id,))
        if row is None:
            return {"error": "task not found"}
        return {
            "task_id": row["id"],
            "status": row["status"],
            "progress": row["progress"],
            "error_msg": row["error_msg"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_task_results(self, task_id: str) -> dict[str, Any]:
        """Get async fetch task result data (JSON from result_data column)."""
        import json as _json

        db = self._get_db()
        row = db.fetchone("SELECT * FROM fetch_task WHERE id=?", (task_id,))
        if row is None:
            return {"error": "task not found"}
        status = row["status"]
        if status == "success":
            data = {}
            if row["result_data"]:
                try:
                    data = _json.loads(row["result_data"])
                except (_json.JSONDecodeError, TypeError):
                    pass
            return {"task_id": task_id, "status": "success", "data": data}
        elif status in ("pending", "running"):
            return {"task_id": task_id, "status": status,
                    "message": "task not yet complete"}
        else:
            return {"task_id": task_id, "status": status,
                    "error": row["error_msg"] or "task failed"}

    def get_announcement_sources(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return distinct announcement records (standard_number + source + title)."""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT DISTINCT standard_number, source_site, std_name, fetched_at "
            "FROM announcement_record ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "standard_number": r["standard_number"],
                "source_site": r["source_site"],
                "title": r["std_name"] or "",
                "fetched_at": r["fetched_at"],
            }
            for r in rows
        ]

    def lookup_announcement(self, number: str) -> dict[str, Any] | None:
        """Exact-match lookup of announcement cache by standard number."""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT standard_number, source_site, std_name, fetched_at "
            "FROM announcement_record WHERE standard_number = ? "
            "ORDER BY fetched_at DESC LIMIT 1",
            (number,),
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "standard_number": r["standard_number"],
            "source_site": r["source_site"],
            "std_name": r["std_name"],
            "fetched_at": r["fetched_at"],
        }

    def _get_db(self) -> Any:
        if self._mgr:
            return self._mgr.db
        return self._file_index._db

    def _get_announcement_stats(self, since: str) -> dict[str, Any]:
        """Query per-source announcement stats (counts + standard totals) since a timestamp."""
        rows = self._file_index._db.fetchall(
            "SELECT source_site, COUNT(*) AS cnt, SUM(standard_count) AS std_cnt "
            "FROM announcement_record WHERE fetched_at >= ? GROUP BY source_site",
            (since,),
        )
        stats: dict[str, Any] = {
            "total_announcements": 0, "total_standards": 0,
            "gb_count": 0, "hb_count": 0, "db_count": 0,
            "gb_standards": 0, "hb_standards": 0, "db_standards": 0,
        }
        for r in rows:
            cnt, std, source = r["cnt"] or 0, r["std_cnt"] or 0, r["source_site"]
            if source == "announcement_gb":
                stats["gb_count"], stats["gb_standards"] = cnt, std
            elif source == "announcement_hb":
                stats["hb_count"], stats["hb_standards"] = cnt, std
            elif source == "announcement_db":
                stats["db_count"], stats["db_standards"] = cnt, std
            stats["total_announcements"] += cnt
            stats["total_standards"] += std
        return stats
