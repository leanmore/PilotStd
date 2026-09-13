# 模块：项目//通知器脚本
"""公告抓取完成后的通知与缓存失效。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnnounceNotifier:
    """纯通知与缓存失效：抓取完成后的副作用处理。"""

    def __init__(self, notification_mgr: Any = None, mgr_db: Any = None):
        self.notification_mgr = notification_mgr
        self.mgr_db = mgr_db

    def after_fetch(self, result: dict[str, Any], source: str = "", since: str = "") -> None:
        """抓取后处理：通知 + 缓存失效。仅在有实际新数据（updated > 0）时失效缓存。

        since：本次抓取起始时间（ISO）。通知明细只展示该窗口内新增的公告，
        为空则不展示明细（宁缺勿错，避免把历史公告当成本次新增）。
        """
        updated = result.get("updated", 0)
        if self.notification_mgr:
            self._send_notifications(result, source, since)
        if self.mgr_db and updated > 0:
            self._invalidate_cache()

    def _fetch_announcement_titles(self, since: str, limit: int = 10) -> list[dict]:
        """查询本次抓取窗口内新增的公告标题（announcement_fetch_complete 明细列表）。

        必须按 since 限定窗口：此前查的是全表最近 fetched 的 10 条公告，
        导致"新增公告：0"却仍列出历史公告，且这些行 fetched_at 不变，
        每次运行原样复现（与手动路径的 fetched_at >= check_start 口径也不一致）。
        """
        if not self.mgr_db or not since:
            return []
        try:
            rows = self.mgr_db.fetchall(
                "SELECT announce_no, announcement_title FROM announcement_record "
                "WHERE fetched_at >= ? AND announcement_title IS NOT NULL AND announcement_title != '' "
                "GROUP BY announce_no ORDER BY announce_no LIMIT ?",
                (since, limit),
            )
            return [
                {"announce_no": r["announce_no"], "title": r["announcement_title"]} for r in rows
            ]
        except Exception:
            return []

    def _send_notifications(self, result: dict[str, Any], source: str, since: str = "") -> None:
        """派发公告检查通知事件：检查汇总 + 全站失败告警 + 逐站明细汇总。"""
        matched = result.get("matched", 0)
        updated = result.get("updated", 0)
        adapters = result.get("adapters", [])
        total = result.get("total_announcements", 0)
        has_error = any(a.get("status") == "error" for a in adapters)
        failure_count = sum(1 for a in adapters if a.get("status") == "error")

        try:
            self.notification_mgr.send_event(
                "announcement_check_complete",
                {
                    "source": source or "手动",
                    "total_announcements": total,
                    "gb_count": result.get("gb_count", 0),
                    "hb_count": result.get("hb_count", 0),
                    "db_count": result.get("db_count", 0),
                    "total_standards": result.get("total_standards", 0),
                    "matched": matched,
                    "updated": updated,
                    "failures": failure_count,
                },
            )
        except Exception as exc:
            logger.warning("公告通知发送失败 (announcement_check_complete): %s", exc)

        # 全站失败（0 条公告且存在失败站点）→ 独立紧急告警（事件本身绕过聚合，实时发送）
        if total == 0 and has_error:
            try:
                self.notification_mgr.send_event(
                    "announcement_fetch_failed",
                    {
                        "source": source or "手动",
                        "error": next(
                            (a.get("error_msg") or "" for a in adapters if a.get("status") == "error"),
                            "所有站点检查失败",
                        ),
                    },
                )
            except Exception as exc:
                logger.warning("公告通知发送失败 (announcement_fetch_failed): %s", exc)

        # 有适配器明细 → 逐站汇总（事件本身绕过聚合，实时发送）
        if adapters:
            try:
                from pilotstd.announce.crawler_service import build_fetch_summary

                self.notification_mgr.send_event("announce_fetch_summary", build_fetch_summary(adapters))
            except Exception as exc:
                logger.warning("公告通知发送失败 (announce_fetch_summary): %s", exc)

        # C-1：定时路径补发"拉取完成"事件（与手动路径对齐），
        # 且与"检查完成"均携带来源字段与新增公告标题明细。
        # 明细仅在本次窗口确有新增公告（total > 0）时附上，杜绝"新增 0 条却列出历史公告"。
        try:
            self.notification_mgr.send_event(
                "announcement_fetch_complete",
                {
                    "count": total,
                    "source": source or "手动",
                    "gb_count": result.get("gb_count", 0),
                    "hb_count": result.get("hb_count", 0),
                    "db_count": result.get("db_count", 0),
                    "announcements": self._fetch_announcement_titles(since) if total > 0 else [],
                },
            )
        except Exception as exc:
            logger.warning("公告通知发送失败 (announcement_fetch_complete): %s", exc)

    def _invalidate_cache(self) -> None:
        """通过 CacheManager 失效公告缓存。"""
        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self.mgr_db).invalidate_by_source(DataSource.ANNOUNCEMENT)
        except Exception as exc:
            logger.warning("公告缓存失效失败: %s", exc)
