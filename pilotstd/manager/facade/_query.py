# 模块：pilotstd/manager/facade/_query.py
"""QueryHandler：标准查询入口与 GUI 桥接。查询执行→QuerySubsystem，报告→QuerySubsystem。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ...core.std_utils import GB_CODES
from ...query.models import BatchQueryStats, QueryResult
from ._query_subsystem import QuerySubsystem

if TYPE_CHECKING:
    from ._core import ManagerCore

logger = logging.getLogger(__name__)


class QueryHandler:
    """查询处理器 — 入口调度与 GUI 桥接方法。

    查询执行与报告统计由 QuerySubsystem 提供（组合注入）。
    """

    def __init__(self, core: "ManagerCore"):
        self._core = core
        self._qs = QuerySubsystem(core)

    # 类常量代理
    _CAT_LABEL = QuerySubsystem._CAT_LABEL
    _PENDING_REASONS = QuerySubsystem._PENDING_REASONS
    _GB_CODES = GB_CODES
    _EXPIRE_STATUSES = frozenset({"废止", "已废止", "作废", "被代替"})

    # ---- 查询执行代理（委托 QuerySubsystem）----

    def query(
        self,
        parsed_list: list[Any] | None = None,
        force_refresh: bool = False,
        progress_callback=None,
        result_callback=None,
        site: str | None = None,
        _adapter: Any = None,
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """批量查询标准的有效性状态。委托 QuerySubsystem。"""
        return self._qs.query(parsed_list, force_refresh, progress_callback, result_callback, site, _adapter)

    def query_stream(
        self,
        parsed_list: list[Any],
        on_progress=None,
        on_result=None,
        site: str | None = None,
        force_refresh: bool = False,
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """流式查询入口，包装 query() 提供流式回调接口。"""
        return self._qs.query_stream(parsed_list, on_progress, on_result, site, force_refresh)

    def record_pending(self, pending_items: list[Any]) -> None:
        self._qs.record_pending(pending_items)

    def _query_announcement_match(self, standard_number: str) -> dict[str, Any] | None:
        return self._qs._query_announcement_match(standard_number)

    def _classify_after_query(self, parsed_list, query_results) -> None:
        self._qs._classify_after_query(parsed_list, query_results)

    def _resolve_replaces(self, standard_number: str) -> str:
        return self._qs._resolve_replaces(standard_number)

    def _report_query_summary(self, stats, items, results) -> None:
        self._qs._report_query_summary(stats, items, results)

    # ---- QuerySubsystem 静态方法代理 ----

    @staticmethod
    def _build_result_from_cache(standard_number: str, cache_data: dict[str, Any]) -> QueryResult:
        return QuerySubsystem._build_result_from_cache(standard_number, cache_data)

    @staticmethod
    def _parse_std_number(standard_number: str) -> tuple[str | None, int | None]:
        return QuerySubsystem._parse_std_number(standard_number)

    # ---- GUI 桥接方法 ----

    def set_pause_event(self, event: Any) -> None:
        self._core.query_engine.set_pause_event(event)

    def get_quota_info(self) -> dict[str, int]:
        return self._core.query_engine.get_quota_info()

    def plan_batch(self, total: int) -> list[tuple[str, int]]:
        return self._core.query_engine.plan_batch(total)

    def get_stage_queue(self, stage: str) -> list[Any]:
        """按阶段获取条目队列（供 GUI 展示）。"""
        if stage == "download":
            return list(self._core.download_list)
        if stage == "expire":
            return list(self._core.expire_list)
        if stage == "pending":
            return list(self._core.pending_list)
        return list(self._core.queried_items) if self._core.queried_items else list(self._core.parsed_results)

    def get_stage_summary(self) -> dict[str, int]:
        """返回各阶段条目数量汇总（供 GUI 展示）。"""
        return {
            "download": len(self._core.download_list),
            "expire": len(self._core.expire_list),
            "pending": len(self._core.pending_list),
            "total": len(self._core.queried_items or self._core.parsed_results),
        }

    def resolve_pending(self, pending_items: list[dict[str, Any]], resolution: str) -> None:
        self._core.pending_svc.resolve_pending(pending_items, resolution)

    def resolve_pending_by_numbers(self, numbers: list[str], resolution: str) -> None:
        self._core.pending_svc.resolve_pending_by_numbers(numbers, resolution)

    def get_pending_items(self) -> list[dict[str, Any]]:
        return self._core.pending_svc.get_pending_items()

    def increment_requery_count(self, standard_number: str) -> int:
        return self._core.pending_svc.increment_requery_count(standard_number)

    def is_requery_exhausted(self, standard_number: str) -> bool:
        return self._core.pending_svc.is_requery_exhausted(standard_number)

    def mark_manual_required(self, standard_number: str) -> None:
        self._core.pending_svc.mark_manual_required(standard_number)

    def get_requery_count(self, standard_number: str) -> int:
        return self._core.pending_svc.get_requery_count(standard_number)

    def query_local_cache(self, parsed_list: list[Any]) -> list[Any]:
        return self._core.pending_svc.query_local_cache(parsed_list)

    def query_by_numbers(
        self, numbers: list[str], force_refresh: bool = False, preferred_site: str | None = None
    ) -> tuple[list[QueryResult], BatchQueryStats]:
        """按标准号列表查询（供 API 层迁移）。"""
        return self._core.scheduled_svc.query_by_numbers(numbers, force_refresh, preferred_site)

    def get_query_sites(self) -> list[str]:
        return self._core.query_engine.get_all_sites()

    def get_site_adapter(self, site_name: str) -> Any:
        return self._core.query_engine.get_adapter(site_name)

    def get_site_cooldown(self, site_name: str) -> float:
        return self._core.query_engine.get_site_cooldown(site_name)

    def get_query_status(self) -> dict[str, bool | int]:
        """返回查询引擎运行状态（供 GUI 展示）。"""
        return {
            "is_running": self._core.query_engine.is_query_running(),
            "overflow_count": self._core.query_engine.get_overflow_count(),
            "csres_active": self._core.query_engine.get_csres_status()["is_active"],
            "is_idle": self._core.query_engine.is_idle(),
        }

    def get_adapter_report(self) -> list[dict[str, Any]]:
        return self._core.db.get_adapter_stats_all()
