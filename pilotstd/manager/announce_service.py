# pilotstd/manager/announce_service.py
# AnnounceService — 公告检查 + 异步抓取任务管理

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any, Optional

from ..announcement.adapters import SamrDbCrawler, SamrGbCrawler, SamrHbCrawler
from ..announcement.engine import AnnounceEngine
from ..announcement.matcher import AnnouncementMatcher
from ..core.config import get_data_dir

logger = logging.getLogger(__name__)


class AnnounceService:
    """公告检查服务 + 异步抓取任务管理。"""

    def __init__(self, file_index: Any, ocr_config: dict[str, Any] | None = None, manager: Any = None):
        self._file_index = file_index
        self._engine: Optional[AnnounceEngine] = None
        self._ocr_config = ocr_config or {}
        self._ocr_provider: Any = None
        self._mgr = manager  # StandardManager 引用（供 API 层迁移使用）

    def _get_ocr_provider(self) -> Any:
        """懒加载 OCR provider，首次调用时从配置创建。"""
        if self._ocr_provider is None and self._ocr_config:
            from ..announcement.ocr import create_ocr_provider

            ocr: Any = create_ocr_provider(self._ocr_config)
            self._ocr_provider = ocr
        return self._ocr_provider

    def _get_or_create_engine(self) -> AnnounceEngine:
        """获取或创建引擎实例（复用）。"""
        if self._engine is None:
            adapters = [SamrGbCrawler(), SamrHbCrawler(), SamrDbCrawler()]
            matcher = AnnouncementMatcher(self._file_index._db)
            self._engine = AnnounceEngine(adapters=adapters, matcher=matcher)
        return self._engine

    def _write_checkpoint(self, source_site: str, last_notice_date: str) -> None:
        """写入 checkpoint，防倒退：空日期不写，旧于当前值不写。"""
        if not last_notice_date:
            return
        current = self._file_index._db.fetchone(
            "SELECT last_notice_date FROM fetch_checkpoint WHERE source_site=?", (source_site,)
        )
        if current and current["last_notice_date"] >= last_notice_date:
            return
        now = datetime.now().isoformat()
        self._file_index._db.execute(
            "INSERT OR REPLACE INTO fetch_checkpoint (source_site, last_fetched_at, last_notice_date) VALUES (?, ?, ?)",
            (source_site, now, last_notice_date),
        )

    # ── 失败记录 ──────────────────────────────────────────

    def _record_fetch_failure(self, task_type: str, source_site: str, since_date: str, error: str) -> None:
        self._file_index._db.execute(
            "INSERT INTO fetch_failures (task_type, source_site, since_date, error_message) VALUES (?, ?, ?, ?)",
            (task_type, source_site, since_date, error),
        )

    # ── 并发锁 ────────────────────────────────────────────

    def _acquire_manual_lock(self) -> bool:
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

    def _after_fetch(self, result: dict[str, Any], source: str = "定时") -> None:
        """抓取后处理：通知 + 缓存失效。"""
        check_start = self._last_check_start if hasattr(self, "_last_check_start") else datetime.now().isoformat()
        stats = self._get_announcement_stats(check_start)
        stats["failures"] = 1 if result.get("error") else 0
        stats["source"] = source
        mgr = self._mgr
        if mgr and mgr.notification_mgr:
            try:
                mgr.notification_mgr.send_event("announcement_check_complete", stats)
            except Exception:
                pass
        if mgr:
            try:
                from ..core.cache_manager import CacheManager, DataSource

                CacheManager(mgr.db).invalidate_by_source(DataSource.ANNOUNCEMENT)
            except Exception:
                pass

    def check_announcements(self) -> dict[str, Any]:
        """检查各公告源的新公告，匹配本地标准，返回 {matched: int, error: str}。"""

        data_dir = get_data_dir()
        for std_type in ("gb", "hb", "db"):
            os.makedirs(os.path.join(data_dir, "announcements", std_type), exist_ok=True)

        engine = self._get_or_create_engine()
        ocr = self._get_ocr_provider()
        total_matched = 0

        for adapter in engine.adapters:
            log_row = self._file_index._db.fetchone(
                "SELECT * FROM fetch_checkpoint WHERE source_site=?", (adapter.source_site,)
            )
            since = log_row["last_notice_date"] if log_row else ""

            result = engine.check_one(adapter.standard_type, since_date=since, ocr_provider=ocr)
            if "error" in result:
                logger.warning("公告适配器 %s 异常: %s", adapter.source_site, result.get("error", ""))
                self._record_fetch_failure("scheduled", adapter.source_site, since, result.get("error", ""))
                continue
            total_matched += result.get("matched", 0)
            self._write_checkpoint(adapter.source_site, result.get("last_notice_date", ""))

        return {"matched": total_matched, "error": ""}

    def check_announcements_filtered(
        self,
        std_type: str | None = None,
        since_date: str = "",
        progress_callback: Any = None,
        types: list[str] | None = None,
    ) -> dict[str, Any]:
        """带类型过滤和日期筛选的公告检查。供 CLI 调用。
        types 参数：限定抓取的公告类型列表，如 ['gb', 'hb']，None 表示全部。"""
        engine = self._get_or_create_engine()
        ocr = self._get_ocr_provider()

        if std_type:
            result = engine.check_one(
                std_type,
                since_date=since_date,
                ocr_provider=ocr,
                progress_callback=progress_callback,
            )
            return {std_type: result}

        # 确定要抓取的适配器列表
        adapters = engine.adapters
        if types:
            adapters = [a for a in adapters if a.standard_type in types]

        results = {}
        for adapter in adapters:
            result = engine.check_one(
                adapter.standard_type,
                since_date=since_date,
                ocr_provider=ocr,
                progress_callback=progress_callback,
            )
            results[adapter.standard_type] = result
            if "error" not in result:
                self._write_checkpoint(adapter.source_site, result.get("last_notice_date", ""))

        return results

    # ── 异步抓取任务管理 ────────────────────────────────

    def trigger_fetch(self, adapter_name: str = "") -> dict[str, Any]:
        """触发异步公告抓取，创建任务并启动后台线程。"""
        import uuid

        db = self._get_db()
        task_id = uuid.uuid4().hex
        now = datetime.now().isoformat()
        db.execute(
            "INSERT INTO fetch_task (id, task_type, status, progress, created_at, updated_at) "
            "VALUES (?, 'announcement', 'pending', 0, ?, ?)",
            (task_id, now, now),
        )
        logger.info("[FETCH_TASK] %s: created (adapter=%s)", task_id, adapter_name or "all")

        t = threading.Thread(target=self._run_fetch_task, args=(task_id, adapter_name), daemon=False)
        t.start()
        return {
            "task_id": task_id,
            "status": "pending",
            "message": f"任务已创建，请轮询 /api/announcements/status/{task_id} 查询进度",
        }

    def _run_fetch_task(self, task_id: str, adapter_name: str) -> None:
        """后台线程：执行公告抓取，更新状态。"""
        import json as _json

        db = self._get_db()
        now = datetime.now().isoformat()
        try:
            db.execute(
                "UPDATE fetch_task SET status='running', progress=10, updated_at=? WHERE id=?",
                (now, task_id),
            )
            logger.info("[FETCH_TASK] %s: running", task_id)

            # 调用同步检查
            result = self.check_with_notification()

            now2 = datetime.now().isoformat()
            if result.get("ok"):
                db.execute(
                    "UPDATE fetch_task SET status='success', progress=100, result_data=?, updated_at=? WHERE id=?",
                    (_json.dumps(result, ensure_ascii=False), now2, task_id),
                )
                logger.info("[FETCH_TASK] %s: success", task_id)
            else:
                db.execute(
                    "UPDATE fetch_task SET status='failed', progress=100, error_msg=?, updated_at=? WHERE id=?",
                    ("抓取完成但返回非 ok", now2, task_id),
                )
                logger.warning("[FETCH_TASK] %s: failed (not ok)", task_id)
        except Exception as e:
            now3 = datetime.now().isoformat()
            db.execute(
                "UPDATE fetch_task SET status='failed', progress=50, error_msg=?, updated_at=? WHERE id=?",
                (str(e), now3, task_id),
            )
            logger.exception("[FETCH_TASK] %s: exception", task_id)

    def check_with_notification(self) -> dict[str, Any]:
        """执行公告检查并发送通知。"""
        self._last_check_start = datetime.now().isoformat()
        result = self.check_announcements()
        stats = self._get_announcement_stats(self._last_check_start)
        stats["failures"] = 1 if result.get("error") else 0
        stats["source"] = "手动"

        # 发送通知
        mgr = self._mgr
        if mgr and mgr.notification_mgr:
            try:
                mgr.notification_mgr.send_event("announcement_check_complete", stats)
                mgr.notification_mgr.send_event(
                    "announcement_fetch_complete",
                    {"count": stats["total_announcements"]},
                )
            except Exception:
                pass

        # 缓存失效
        if mgr:
            try:
                from ..core.cache_manager import CacheManager, DataSource

                CacheManager(mgr.db).invalidate_by_source(DataSource.ANNOUNCEMENT)
            except Exception:
                pass

        return {"ok": True, "count": stats["total_announcements"], "failures": stats["failures"]}

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
        """获取公告抓取记录（去重，供 API 层迁移）。"""
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
        """按标准号精确查询公告缓存（供 API 层迁移）。"""
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
        """获取数据库连接。优先使用 Manager 的 DB，回退到 file_index 的 DB。"""
        if self._mgr:
            return self._mgr.db
        return self._file_index._db

    def _get_announcement_stats(self, since: str) -> dict[str, Any]:
        """从 announcement_record 表查询 since 之后新增公告的分类统计。"""
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
            cnt = r["cnt"] or 0
            std = r["std_cnt"] or 0
            source = r["source_site"]
            if source == "announcement_gb":
                stats["gb_count"] = cnt
                stats["gb_standards"] = std
            elif source == "announcement_hb":
                stats["hb_count"] = cnt
                stats["hb_standards"] = std
            elif source == "announcement_db":
                stats["db_count"] = cnt
                stats["db_standards"] = std
            stats["total_announcements"] += cnt
            stats["total_standards"] += std
        return stats
