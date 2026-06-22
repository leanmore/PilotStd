# pilotstd/announcement/engine.py
# 公告引擎 — 编排多个适配器，GB→HB→DB 串行抓取

import logging
from typing import Any

from .base import BaseAnnounceAdapter
from .matcher import AnnouncementMatcher

logger = logging.getLogger(__name__)


class AnnounceEngine:
    """公告抓取编排器。GB→HB→DB 依次串行执行。

    三个适配器共用同一 SAMR 域名，串行避免并发冲击。
    引擎实例可复用（通过 AnnounceService 缓存）。
    """

    def __init__(
        self, adapters: list[BaseAnnounceAdapter], matcher: AnnouncementMatcher
    ):
        self._adapters = {a.standard_type: a for a in adapters}
        self._matcher = matcher

    @property
    def adapters(self) -> list[BaseAnnounceAdapter]:
        """返回适配器列表，供 AnnounceService 遍历。"""
        return list(self._adapters.values())

    def check_all(
        self, since_date: str = "", ocr_provider: Any = None
    ) -> dict[str, dict[str, Any]]:
        """GB→HB→DB 依次串行抓取。
        返回 {gb: {matched, updated}, hb: ..., db: ...}。
        """
        result = {}
        for std_type in ("gb", "hb", "db"):
            adapter = self._adapters.get(std_type)
            if adapter is None:
                continue
            try:
                result[std_type] = self._check_one_adapter(
                    adapter, since_date, ocr_provider=ocr_provider
                )
            except Exception as e:
                logger.error("公告适配器 %s 异常: %s", std_type, e)
                result[std_type] = {
                    "matched": 0,
                    "updated": 0,
                    "total_announcements": 0,
                    "last_notice_date": "",
                    "error": str(e),
                }
        return result

    def check_one(
        self,
        standard_type: str,
        since_date: str = "",
        ocr_provider: Any = None,
        progress_callback: Any = None,
        checkpoint_pids: Any = None,
    ) -> dict[str, Any]:
        """指定类型抓取。"""
        adapter = self._adapters.get(standard_type)
        if adapter is None:
            return {"error": f"未知公告类型: {standard_type}"}
        return self._check_one_adapter(
            adapter,
            since_date,
            ocr_provider=ocr_provider,
            progress_callback=progress_callback,
            checkpoint_pids=checkpoint_pids,
        )

    def _check_one_adapter(
        self,
        adapter: BaseAnnounceAdapter,
        since_date: str,
        ocr_provider: Any = None,
        progress_callback: Any = None,
        checkpoint_pids: Any = None,
    ) -> dict[str, Any]:
        try:
            items = adapter.fetch_announcements(
                since_date=since_date,
                ocr_provider=ocr_provider,
                progress_callback=progress_callback,
                checkpoint_pids=checkpoint_pids,
            )
        except Exception as e:
            logger.error("公告适配器 %s 异常: %s", adapter.source_site, e)
            return {
                "matched": 0,
                "updated": 0,
                "total_announcements": 0,
                "last_notice_date": "",
                "error": str(e),
            }
        if not items:
            return {
                "matched": 0,
                "updated": 0,
                "total_announcements": 0,
                "last_notice_date": "",
            }
        result = self._matcher.match_and_update(items, source_site=adapter.source_site)
        result["total_announcements"] = len(items)
        max_date = ""
        for item in items:
            d = item.get("notice_date", "")
            if d and d > max_date:
                max_date = d
        result["last_notice_date"] = max_date
        return result
