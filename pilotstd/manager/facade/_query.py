# pilotstd/manager/facade/_query.py
"""QueryHandler：标准查询入口与 GUI 桥接。查询执行→_query_exec，报告→_query_report。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ...core.std_utils import GB_CODES
from ...query.models import BatchQueryStats, QueryResult
from ._query_exec import _QueryExecMixin
from ._query_report import _QueryReportMixin

if TYPE_CHECKING:
    from ._core import ManagerCore

logger = logging.getLogger(__name__)


class QueryHandler(_QueryExecMixin, _QueryReportMixin):
    """查询处理器 — 入口调度与 GUI 桥接方法。

    查询执行由 _QueryExecMixin 提供，报告统计由 _QueryReportMixin 提供。
    """

    def __init__(self, core: "ManagerCore"):
        self._core = core

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

    def set_pause_event(self, event: Any) -> None:
        self._core.query_engine.set_pause_event(event)

    # ── GUI 桥接方法 ──

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

    # ── 待确认清单 ──

    def record_pending(self, pending_items: list[Any]) -> None:
        self._core.pending_svc.record_pending(pending_items)

    def resolve_pending(self, pending_items: list[dict[str, Any]], resolution: str) -> None:
        self._core.pending_svc.resolve_pending(pending_items, resolution)

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

    # ── 引擎状态查询 ──

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
