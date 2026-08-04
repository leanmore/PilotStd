# 模块：pilotstd/announcement/engine.py
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
        # 用 dict 按 standard_type 索引，O(1) 查找适配器
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

        # 三个适配器独立抓取，互不阻塞，用线程池并发
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for std_type in std_types:
                adapter = self._adapters.get(std_type)
                if adapter is None:
                    continue
                # 提交抓取任务，future→std_type 映射用于收集结果时识别来源
                futures[executor.submit(self._check_one_adapter, adapter, since_date, ocr_provider)] = std_type

            for future in concurrent.futures.as_completed(futures):
                std_type = futures[future]
                try:
                    result[std_type] = future.result()
                except Exception:
                    # 单个适配器失败不影响其他适配器，记录异常后填默认兜底值
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
        """查单个公告类型（gb/hb/db），返回匹配和更新统计。"""
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
        """单适配器运行：跳过已完全解析的公告 → 抓取 → 交叉比对。"""
        # 先查已完全解析的 PID，跳过重复抓取详情页以节省资源
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
        # 交叉比对：将公告清单与本地 file_index 匹配，更新缓存
        result = self._matcher.match_and_update(items, source_site=adapter.source_site)
        result["total_announcements"] = len(items)
        # 提取本次抓取中最晚的公告日期，用于下次抓取的 since_date 基准
        max_date = ""
        for item in items:
            d = item.get("notice_date", "")
            if d and d > max_date:
                max_date = d
        result["last_notice_date"] = max_date
        return result
