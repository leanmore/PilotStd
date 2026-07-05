# pilotstd/announcement/engine.py
# 公告引擎 — 编排多个适配器，GB/HB/DB 并发抓取

import concurrent.futures
import logging
from typing import Any

from .base import BaseAnnounceCrawler
from .matcher import AnnouncementMatcher

logger = logging.getLogger(__name__)


class AnnounceEngine:
    """公告抓取编排器。GB/HB/DB 并发执行，互不阻塞。"""

    def __init__(self, adapters: list[BaseAnnounceCrawler], matcher: AnnouncementMatcher):
        self._adapters = {a.standard_type: a for a in adapters}
        self._matcher = matcher

    @property
    def adapters(self) -> list[BaseAnnounceCrawler]:
        return list(self._adapters.values())

    def check_all(self, since_date: str = "", ocr_provider: Any = None) -> dict[str, dict[str, Any]]:
        """GB/HB/DB 并发抓取，单个失败不影响其他。
        返回 {gb: {matched, updated}, hb: ..., db: ...}。
        """
        result: dict[str, dict[str, Any]] = {}
        std_types = ("gb", "hb", "db")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for std_type in std_types:
                adapter = self._adapters.get(std_type)
                if adapter is None:
                    continue
                futures[executor.submit(self._check_one_adapter, adapter, since_date, ocr_provider)] = std_type

            for future in concurrent.futures.as_completed(futures):
                std_type = futures[future]
                try:
                    result[std_type] = future.result()
                except Exception:
                    logger.exception("公告适配器 %s 异常", std_type)
                    result[std_type] = {
                        "matched": 0,
                        "updated": 0,
                        "total_announcements": 0,
                        "last_notice_date": "",
                        "error": "执行异常",
                    }

        return result

    def check_one(
        self,
        standard_type: str,
        since_date: str = "",
        ocr_provider: Any = None,
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        adapter = self._adapters.get(standard_type)
        if adapter is None:
            return {"error": f"未知公告类型: {standard_type}"}
        return self._check_one_adapter(adapter, since_date, ocr_provider, progress_callback)

    def _check_one_adapter(
        self,
        adapter: BaseAnnounceCrawler,
        since_date: str,
        ocr_provider: Any = None,
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        complete_pids = self._matcher._get_complete_pids(adapter.source_site)
        logger.info("公告 %s: 已完全解析 %d 条，将跳过详情页抓取", adapter.standard_type, len(complete_pids))
        try:
            items = adapter.fetch_announcements(
                since_date=since_date,
                ocr_provider=ocr_provider,
                progress_callback=progress_callback,
                complete_pids=complete_pids,
            )
        except Exception:
            logger.exception("公告适配器 %s 抓取异常", adapter.source_site)
            return {"matched": 0, "updated": 0, "total_announcements": 0, "last_notice_date": "", "error": "抓取异常"}
        if not items:
            return {"matched": 0, "updated": 0, "total_announcements": 0, "last_notice_date": ""}
        result = self._matcher.match_and_update(items, source_site=adapter.source_site)
        result["total_announcements"] = len(items)
        max_date = ""
        for item in items:
            d = item.get("notice_date", "")
            if d and d > max_date:
                max_date = d
        result["last_notice_date"] = max_date
        return result
