# pilotstd/manager/facade/_query_exec.py
# 查询执行混入 — 从 _query.py 提取
# 公告缓存查询、引擎查询、流式查询、结果终结处理

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

import requests

from ...query.models import BatchQueryStats, QueryResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class _QueryExecMixin:
    """查询执行方法集合（混入 QueryHandler）。"""

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

    # ── 公告缓存优先模式 ──

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
                    standard_number=f"{p.logical_code} {p.number}{part_str}-{p.year}",
                    error_message="查询未执行",
                )
        return results

    # ── 引擎直查模式 ──

    def _query_via_engine(
        self,
        items: list[Any],
        result_callback: Callable[[int, Any], None] | None,
        site: str | None = None,
        force_refresh: bool = False,
        progress_callback: Callable[[int], None] | None = None,
    ) -> list[QueryResult]:
        """直接调用 QueryEngine 查询（无公告缓存的默认路径）。"""
        # 将 ParsedStdInfo 列表转换为引擎期望的元组格式
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

    # ── 结果终结处理 ──

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

        self._classify_after_query(items, results)
        if self._core.pending_list:
            self.record_pending(self._core.pending_list)
        self._report_query_summary(stats, items, results)

        try:
            pending_count = len(self._core.pending_list)
            if self._core.notification_mgr:
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

    # ── 流式查询入口 ──

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
