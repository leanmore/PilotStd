# pilotstd/manager/announce_service.py
# AnnounceService — 公告检查入口与任务状态查询
# 抓取/检查方法已提取至 _announce_fetch.py

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from ..announcement.engine import AnnounceEngine
from ._announce_fetch import _AnnounceFetchMixin

logger = logging.getLogger(__name__)


class AnnounceService(_AnnounceFetchMixin):
    """公告检查服务。抓取/检查方法由 _AnnounceFetchMixin 提供。"""

    def __init__(self, file_index: Any, ocr_config: dict[str, Any] | None = None, manager: Any = None):
        self._engine: Optional[AnnounceEngine] = None
        self._ocr_config = ocr_config or {}
        self._ocr_provider: Any = None
        self._mgr = manager
        self._file_index = file_index

    # ── 并发锁 ────────────────────────────────────────────

    def _acquire_manual_lock(self) -> bool:
        """获取手动抓取锁，防止定时任务与手动抓取冲突。"""
        try:
            self._file_index._db.execute(
                "INSERT OR REPLACE INTO fetch_locks (lock_key, locked_at, locked_by) VALUES ('manual', ?, 'manual')",
                (datetime.now().isoformat(),),
            )
            return True
        except Exception:
            return False

    def _release_manual_lock(self) -> None:
        self._file_index._db.execute("DELETE FROM fetch_locks WHERE lock_key='manual'")

    def _is_manual_running(self) -> bool:
        row = self._file_index._db.fetchone("SELECT 1 FROM fetch_locks WHERE lock_key='manual'")
        return row is not None

    # ── 用户偏好 ──────────────────────────────────────────

    def _get_user_since_date(self) -> str:
        row = self._file_index._db.fetchone("SELECT value FROM app_preferences WHERE key='announce_since_date'")
        return row["value"] if row and row["value"] else ""

    def _clear_user_since_date(self) -> None:
        self._file_index._db.execute("UPDATE app_preferences SET value='' WHERE key='announce_since_date'")

    def save_user_preference(self, key: str, value: str) -> None:
        """保存用户偏好键值对。"""
        self._file_index._db.execute(
            "INSERT OR REPLACE INTO app_preferences (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )

    # ── 定时任务统一入口 ──────────────────────────────────

    def check_announce_scheduled(self) -> dict[str, Any]:
        """定时任务统一入口：避让手动 → 补抓队列 → 用户日期回填 → 增量抓取。"""
        if self._is_manual_running():
            logger.info("手动抓取正在运行，定时任务跳过本次")
            return {"skipped": True, "reason": "manual_running"}

        self._last_check_start = datetime.now().isoformat()

        user_since = self._get_user_since_date()
        if user_since:
            logger.info("定时任务检测到用户设定起始日期: %s，执行回填抓取", user_since)
            result = self.check_announcements_filtered(since_date=user_since)
            self._clear_user_since_date()
        else:
            result = self.check_announcements()

        self._after_fetch(result, source="定时")
        return result

    # ── 任务状态查询 ──────────────────────────────────────

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """查询异步抓取任务进度。"""
        db = self._get_db()
        row = db.fetchone("SELECT * FROM fetch_task WHERE id=?", (task_id,))
        if row is None:
            return {"error": "任务不存在"}
        return {
            "task_id": row["id"],
            "status": row["status"],
            "progress": row["progress"],
            "error_msg": row["error_msg"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_task_results(self, task_id: str) -> dict[str, Any]:
        """获取异步抓取任务的结果数据。"""
        import json as _json

        db = self._get_db()
        row = db.fetchone("SELECT * FROM fetch_task WHERE id=?", (task_id,))
        if row is None:
            return {"error": "任务不存在"}
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
            return {"task_id": task_id, "status": status, "message": "任务尚未完成，请稍后再试"}
        else:
            return {"task_id": task_id, "status": status, "error": row["error_msg"] or "任务执行失败"}

    def get_announcement_sources(self, limit: int = 200) -> list[dict[str, Any]]:
        """获取公告抓取记录列表。"""
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
        """按标准号精确查询公告缓存。"""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT standard_number, source_site, std_name, fetched_at "
            "FROM announcement_record WHERE standard_number = ? ORDER BY fetched_at DESC LIMIT 1",
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
        """查询指定时间后的公告分类统计。"""
        rows = self._file_index._db.fetchall(
            "SELECT source_site, COUNT(*) AS cnt, SUM(standard_count) AS std_cnt "
            "FROM announcement_record WHERE fetched_at >= ? GROUP BY source_site",
            (since,),
        )
        stats: dict[str, Any] = {
            "total_announcements": 0,
            "total_standards": 0,
            "gb_count": 0,
            "hb_count": 0,
            "db_count": 0,
            "gb_standards": 0,
            "hb_standards": 0,
            "db_standards": 0,
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
