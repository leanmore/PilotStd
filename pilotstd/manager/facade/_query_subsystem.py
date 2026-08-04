# pilotstd/manager/facade/_query_subsystem.py
"""QuerySubsystem — 查询执行 + 报告统计的组合类。

原 _QueryExecMixin + _QueryReportMixin，合并为独立类（组合注入到 QueryHandler）。
交叉调用原来通过 MRO（self._classify_after_query 等），现在同一 self 上直接调用。
模块依赖: requests (HTTP), core.std_utils (分类), query.models (数据类)
"""

# 设计决策: 为何不拆为 QueryExecutor + QueryReporter 两个类？
# 两个原 Mixin 之间存在单向交叉调用 (_finalize_query → _classify_after_query / _report_query_summary)，
# 拆分会引入循环依赖或额外的回调注册。合并保持内聚性。

from __future__ import annotations

import logging
from typing import Any, Callable

import requests

from ...core.std_utils import GB_CODES, classify_std_code
from ...query.models import BatchQueryStats, QueryResult

logger = logging.getLogger(__name__)


class QuerySubsystem:
    """查询执行与报告统计。组合注入到 QueryHandler。"""

    # 原定义在 QueryHandler 上的类常量
    _CAT_LABEL = {
        "gb": "国标",
        "industry": "行业标准",
        "db": "地方标准",
        "iso_iec": "国际标准",
        "foreign": "国外标准",
        "group": "团体标准",
        "enterprise": "企业标准",
    }

    _PENDING_REASONS = {
        "older": "站点仅有更旧版本，未找到对应年份",
        "newer": "站点版本比本地文件更新",
        "code_only": "站点仅匹配到代号，标准号/年份不一致",
        "mismatch": "站点返回的标准名称与文件名不匹配",
    }

    _GB_CODES = GB_CODES
    _EXPIRE_STATUSES = frozenset({"废止", "已废止", "作废", "被代替"})

    def __init__(self, core):
        self._core = core

    # ══════════════════════════════════════════════════════════
    # 原 _QueryExecMixin 方法
    # ══════════════════════════════════════════════════════════

    def _query_announcement_match(self, standard_number: str) -> dict[str, Any] | None:
        """向 Web 端公告缓存服务查询单个标准号。"""
        base_url = self._core.cfg.get("query.announcement_url", "http://localhost:9028")
        timeout = self._core.cfg.get("network.timeout", 30)
        api_key = self._core.cfg.get("query.announcement_api_key", "")
        if not api_key or not api_key.strip():
            return None
        url = f"{base_url.rstrip('/')}/api/announce/lookup"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = requests.get(url, params={"number": standard_number}, timeout=timeout, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        except requests.exceptions.Timeout:
            logger.info("公告缓存查询：%s → 超时，降级到实时网络查询", standard_number)
            return None
        except requests.exceptions.ConnectionError as e:
            logger.info("公告缓存查询：%s → 连接失败（%s），降级到实时网络查询", standard_number, e)
            return None
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.info("公告缓存查询：%s → 异常（%s），降级到实时网络查询", standard_number, e)
            return None

        if body.get("found"):
            logger.info("公告缓存查询：%s → 命中", standard_number)
            return {"data": body["data"], "cached_at": body.get("cached_at", "")}
        logger.info("公告缓存查询：%s → 未命中", standard_number)
        return None

    @staticmethod
    def _build_result_from_cache(standard_number: str, cache_data: dict[str, Any]) -> QueryResult:
        """从 Web 公告缓存数据构建 QueryResult。"""
        data = cache_data or {}
        return QueryResult(
            standard_number=standard_number,
            standard_name=data.get("standard_name", data.get("std_name", "")),
            status=data.get("status", data.get("effect_status", "")),
            replaces=data.get("replaces", data.get("replaces_code", "")),
            implementation_date=data.get("implementation_date", ""),
            responsible_dept=data.get("responsible_dept", ""),
            is_adopted=data.get("is_adopted", False),
            match_status=data.get("match_status", "exact"),
            source_site="web_announcement_match",
            source="web端公告缓存",
            publish_date=data.get("publish_date", ""),
            abolition_date=data.get("abolition_date", ""),
            hcno=data.get("hcno", ""),
            is_downloadable=data.get("is_downloadable", True),
        )

    def _query_via_cache(
        self,
        items: list[Any],
        result_callback: Callable[[int, Any], None] | None,
        progress_callback: Callable[[int], None] | None = None,
    ) -> list[QueryResult]:
        """公告缓存优先模式：先查 Web 缓存，未命中降级到实时引擎。"""
        cache_hit_map: dict[int, QueryResult] = {}
        miss_indices: list[int] = []
        miss_items: list[Any] = []

        for i, p in enumerate(items):
            part = getattr(p, "part", None)
            part_str = f".{part}" if part else ""
            std_num = f"{p.logical_code} {p.number}{part_str}-{p.year}"
            cache_hit = self._query_announcement_match(std_num)
            if cache_hit:
                cache_hit_map[i] = self._build_result_from_cache(std_num, cache_hit["data"])
                if result_callback:
                    result_callback(i, cache_hit_map[i])
            else:
                miss_indices.append(i)
                miss_items.append(p)

        _placeholder = QueryResult(standard_number="")
        results: list[QueryResult] = [_placeholder] * len(items)
        for i, r in cache_hit_map.items():
            results[i] = r

        if miss_items:
            miss_tuples = [
                (
                    p.logical_code,
                    p.number,
                    p.year,
                    p.std_name or "",
                    getattr(p, "part", None),
                    getattr(p, "num_prefix", ""),
                    getattr(p, "num_suffix", ""),
                    getattr(p, "source_path", ""),
                )
                for p in miss_items
            ]

            # 闭包：将 miss_idx 映射回原始索引，回填到 results 列表
            def _fallback_callback(miss_idx: int, r: QueryResult) -> None:
                """未命中缓存时降级到实时引擎，将结果回填到正确位置。"""
                r.source = "live_fallback"
                orig_idx = miss_indices[miss_idx]
                results[orig_idx] = r
                if result_callback:
                    result_callback(orig_idx, r)

            engine_results = self._core.query_engine.query_standards(
                miss_tuples,
                result_callback=_fallback_callback,
                progress_callback=progress_callback,
            )
            for j, r in enumerate(engine_results):
                orig_idx = miss_indices[j]
                if results[orig_idx] is _placeholder:
                    r.source = "live_fallback"
                    results[orig_idx] = r

        for i in range(len(results)):
            if results[i] is _placeholder:
                p = items[i]
                part_str = f".{getattr(p, 'part', '')}" if getattr(p, "part", None) else ""
                results[i] = QueryResult(
                    standard_number=f"{p.logical_code} {p.raw_number or str(p.number)}{part_str}-{p.year}",
                    error_message="查询未执行",
                )
        return results

    def _query_via_engine(
        self,
        items: list[Any],
        result_callback: Callable[[int, Any], None] | None,
        site: str | None = None,
        force_refresh: bool = False,
        progress_callback: Callable[[int], None] | None = None,
    ) -> list[QueryResult]:
        """直接调用 QueryEngine 查询（无公告缓存的默认路径）。"""
        parsed_tuples = [
            (p.logical_code, p.number, p.year, p.std_name or "", p.part, getattr(p, "num_prefix", "")) for p in items
        ]
        return self._core.query_engine.query_standards(
            parsed_tuples,
            result_callback=result_callback,
            progress_callback=progress_callback,
            preferred_site=site,
            force_refresh=force_refresh,
        )

    def _finalize_query(
        self, items: list[Any], results: list[QueryResult]
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """统计 + 分类路由 + 待确认持久化 + 汇总报告。"""
        self._core.query_results = results
        stats = BatchQueryStats()
        stats.total = len(items)
        for r in results:
            if r.is_found():
                stats.found += 1
            if r.is_downloadable:
                stats.downloadable += 1
            if getattr(r, "is_adopted", False):
                stats.adopted_restricted += 1
            if getattr(r, "match_status", "") == "exact":
                stats.exact += 1

        failed_items = [
            (r.standard_number, getattr(r, "error_message", "") or "未知错误")
            for r in results
            if getattr(r, "error_message", "") and r.standard_number
        ]
        try:
            if self._core.notification_mgr and failed_items:
                for std_no, err in failed_items[:5]:
                    self._core.notification_mgr.send_event(
                        "query_failed",
                        {"standard_number": std_no, "error": err},
                    )
        except Exception:
            pass

        self._classify_after_query(items, results)
        if self._core.pending_list:
            self.record_pending(self._core.pending_list)
        self._report_query_summary(stats, items, results)

        try:
            pending_count = len(self._core.pending_list)
            if self._core.notification_mgr:
                if stats.found == 0 and stats.total > 0:
                    self._core.notification_mgr.send_event(
                        "query_empty",
                        {"total": stats.total},
                    )
                else:
                    self._core.notification_mgr.send_event(
                        "batch_query_summary",
                        {"total": stats.total, "found": stats.found, "pending": pending_count},
                    )
        except Exception:
            pass
        return results, stats

    def query(
        self,
        parsed_list: list[Any] | None = None,
        force_refresh: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
        result_callback: Callable[[int, Any], None] | None = None,
        site: str | None = None,
        _adapter: Any = None,
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """批量查询标准的有效性状态。"""
        items = parsed_list or self._core.parsed_results
        self._core.queried_items = items
        total = len(items)
        engine_progress: Callable[[int], None] | None = None
        if progress_callback and total > 0:

            def _engine_progress(count: int) -> None:
                progress_callback(count, total)

            engine_progress = _engine_progress

        if site or not self._core.cfg.get("query.use_announcement_match", False):
            results = self._query_via_engine(
                items,
                result_callback,
                site=site,
                force_refresh=force_refresh,
                progress_callback=engine_progress,
            )
        else:
            results = self._query_via_cache(items, result_callback, progress_callback=engine_progress)

        return self._finalize_query(items, results)

    def query_stream(
        self,
        parsed_list: list[Any],
        on_progress: Callable[[int, int], None] | None = None,
        on_result: Callable[[int, Any], None] | None = None,
        site: str | None = None,
        force_refresh: bool = False,
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """流式查询（线程安全），包装 query() 提供流式回调接口。"""
        return self.query(
            parsed_list=parsed_list,
            force_refresh=force_refresh,
            progress_callback=on_progress,
            result_callback=on_result,
            site=site,
        )

    # ══════════════════════════════════════════════════════════
    # 原 _QueryReportMixin 方法
    # ══════════════════════════════════════════════════════════

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
            notification_mgr=self._core.notification_mgr,
        )

    def _resolve_replaces(self, standard_number: str) -> str:
        """跨站点补查替代关系。"""
        return self._core.classifier.resolve_replaces(standard_number)

    # ══════════════════════════════════════════════════════════
    # 原 QueryHandler 上的方法（被 _finalize_query 调用）
    # ══════════════════════════════════════════════════════════

    def record_pending(self, pending_items: list[Any]) -> None:
        """待确认清单持久化。"""
        self._core.pending_svc.record_pending(pending_items)
