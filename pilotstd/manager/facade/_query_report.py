# pilotstd/manager/facade/_query_report.py
# 查询报告混入 — 从 _query.py 提取
# 分类统计、下载队列统计、汇总报告、分类路由

from __future__ import annotations

import logging
from typing import Any

from ...core.std_utils import classify_std_code
from ...query.models import BatchQueryStats, QueryResult

logger = logging.getLogger(__name__)


class _QueryReportMixin:
    """查询报告与分类方法集合（混入 QueryHandler）。"""

    def _report_category_breakdown(self, items: list[Any], results: list[QueryResult]) -> None:
        """按标准类型分组统计：国标/行业/地方/国际/国外，含待确认计数。"""
        cats: dict[str, dict[str, int]] = {}
        for p, r in zip(items, results):
            cat = self._CAT_LABEL.get(classify_std_code(p.logical_code), "未知")
            if cat not in cats:
                cats[cat] = {"total": 0, "found": 0, "pending": 0}
            cats[cat]["total"] += 1
            if r.is_found():
                cats[cat]["found"] += 1
        pending_set = set(id(p) for p in self._core.pending_list)
        for p in items:
            cat = self._CAT_LABEL.get(classify_std_code(p.logical_code), "未知")
            if id(p) in pending_set:
                cats[cat]["pending"] += 1

        for cat in ("国标", "行业标准", "地方标准", "国际标准", "国外标准", "未知"):
            c = cats.pop(cat, None)
            if c is None:
                continue
            pct = c["found"] / max(c["total"], 1) * 100
            parts = [f"{cat}: {c['found']}/{c['total']} 找到 ({pct:.1f}%)"]
            if c["pending"]:
                parts.append(f"其中 {c['pending']} 待确认")
            logger.info("  " + ", ".join(parts))
        for cat, c in cats.items():
            pct = c["found"] / max(c["total"], 1) * 100
            logger.info(
                "  %s: %d/%d 找到 (%.1f%%)%s",
                cat,
                c["found"],
                c["total"],
                pct,
                f"，其中 {c['pending']} 待确认" if c["pending"] else "",
            )

    def _report_download_queue(self, items: list[Any], results: list[QueryResult]) -> None:
        """统计下载队列：采标跳过、国外/国际无下载源、废止标记、待确认。"""
        dl = len(self._core.download_list)
        expire = len(self._core.expire_list)
        pending = len(self._core.pending_list)
        # 分别统计采标跳过的和国际/国外无下载源的条目
        adopted_skip = 0
        foreign_skip = 0
        for p, r in zip(items, results):
            if not r.is_found():
                continue
            if getattr(r, "is_adopted", False):
                adopted_skip += 1
            else:
                cat = classify_std_code(p.logical_code)
                if cat in ("foreign", "iso_iec"):
                    foreign_skip += 1
        reason_parts = []
        if adopted_skip:
            reason_parts.append(f"{adopted_skip} 条因采标无法下载")
        if foreign_skip:
            reason_parts.append(f"{foreign_skip} 条因国外/国际标准无国内下载源")
        reason_str = "；".join(reason_parts) if reason_parts else "无可下载项"
        logger.info("  进入下载队列: %d, 标记废止: %d, 待确认: %d  (%s)", dl, expire, pending, reason_str)

    def _report_query_summary(self, stats: BatchQueryStats, items: list[Any], results: list[QueryResult]) -> None:
        """输出查询阶段汇总报告。"""
        n = len(items)
        logger.info("查询完成: %d/%d 找到 (%.1f%%)", stats.found, n, stats.found / max(n, 1) * 100)
        logger.info("%d 精确匹配", stats.exact)
        self._report_category_breakdown(items, results)

        pending_by_reason: dict[str, int] = {}
        for r in results:
            ms = getattr(r, "match_status", "") or ""
            if ms == "exact" or not ms:
                continue
            pending_by_reason[ms] = pending_by_reason.get(ms, 0) + 1
        if pending_by_reason:
            logger.info("  待确认 %d 条:", sum(pending_by_reason.values()))
            for ms, cnt in sorted(pending_by_reason.items(), key=lambda x: -x[1]):
                reason = self._PENDING_REASONS.get(ms, ms)
                logger.info("    %s: %d 条  (%s)", ms, cnt, reason)

        site_count: dict[str, int] = {}
        for r in results:
            site = getattr(r, "source_site", "") or ""
            if site and r.is_found():
                site_count[site] = site_count.get(site, 0) + 1
        if site_count:
            parts = [f"{s}={c}" for s, c in sorted(site_count.items(), key=lambda x: -x[1])]
            logger.info("  站点贡献: %s", "  ".join(parts))
        self._report_download_queue(items, results)

    @staticmethod
    def _parse_std_number(standard_number: str) -> tuple[str | None, int | None]:
        """从标准号字符串中提取代号和序号。"""
        from ..classifier import QueryClassifier

        return QueryClassifier.parse_std_number(standard_number)

    def _classify_after_query(self, parsed_list: list[Any], query_results: list[QueryResult]) -> None:
        """查询后分类：委托 classifier 统一分堆。"""
        self._core.classifier.classify(
            query_results,
            parsed_list,
            self._core.download_list,
            self._core.expire_list,
            self._core.pending_list,
        )

    def _resolve_replaces(self, standard_number: str) -> str:
        """跨站点补查替代关系。"""
        return self._core.classifier.resolve_replaces(standard_number)
