# pilotstd/manager/_announce_fetch.py
# 公告抓取与检查混入 — 从 announce_service.py 提取

import logging
import os
import threading
import uuid
from datetime import datetime
from typing import Any

from ..announcement.adapters import SamrDbCrawler, SamrGbCrawler, SamrHbCrawler
from ..announcement.engine import AnnounceEngine
from ..announcement.matcher import AnnouncementMatcher
from ..core.config import get_data_dir

logger = logging.getLogger(__name__)


class _AnnounceFetchMixin:
    """公告抓取与检查方法集合（混入 AnnounceService）。

    所有方法通过 self._file_index、self._mgr、self._engine、self._ocr_provider 访问共享状态。
    """

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
        """记录一次抓取失败到 fetch_failures 表。"""
        self._file_index._db.execute(
            "INSERT INTO fetch_failures (task_type, source_site, since_date, error_message) VALUES (?, ?, ?, ?)",
            (task_type, source_site, since_date, error),
        )

    # ── 并发锁 ────────────────────────────────────────────

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
            try:
                # 全站点失败时发送独立失败通知
                if stats.get("total_announcements", 0) == 0 and stats.get("failures", 0) > 0:
                    mgr.notification_mgr.send_event(
                        "announcement_fetch_failed",
                        {"source": source, "error": result.get("error", "所有站点检查失败")},
                    )
            except Exception:
                pass
        if mgr:
            try:
                from ..core.cache_manager import CacheManager, DataSource

                CacheManager(mgr.db).invalidate_by_source(DataSource.ANNOUNCEMENT)
            except Exception:
                pass

    # ── 公告增量检查 ──────────────────────────────────────

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

    # ── 任务状态查询 ──────────────────────────────────────
