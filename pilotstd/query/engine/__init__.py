# 模块：项目/查询/引擎/____脚本
# 说明：:--="--"
"""查询引擎 — 组合模式重构。

QueryEngine 通过组合 Handler（RoutingHandler、SingleQueryHandler、BatchHandler、
CsresHandler、MiniBucketHandler、OverflowHandler、ReportHandler）
替代原有的 Mixin 继承模式，所有依赖通过 EngineCore 容器管理。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

from ..models import QueryResult
from ._batch import BatchHandler
from ._constants import _DEFAULT_FALLBACK_CHAIN, CODE_ROUTES, PROGRESS_TAG
from ._core import QueryEngineCore
from ._core_types import EngineCore
from ._csres import CsresHandler
from ._mini_bucket import MiniBucketHandler
from ._overflow import OverflowHandler
from ._report import ReportHandler
from ._routing import RoutingHandler
from ._single import SingleQueryHandler

if TYPE_CHECKING:
    from ...scan.parser import StandardParser
    from ..adapters.base import BaseAdapter
    from ..cache import CacheRepository
    from ..daily_quota import DailyQuotaTracker
    from ..rotator import SiteRotator

logger = logging.getLogger(__name__)


class QueryEngine(QueryEngineCore):
    """查询引擎 — 统一查询入口。

    继承 QueryEngineCore 获得 _core 容器和基础方法，
    通过组合 Handler 获得所有查询功能，替代原 Mixin 继承。

    对外 API 保持不变：
        - query_standards() / query_batch_parsed()
        - get_quota_info() / get_all_sites() / get_adapter()
        - get_site_cooldown() / get_query_status()
        - get_csres_status() / get_overflow_count()
        - is_idle() / is_query_running() / plan_batch()
        - set_pause_event()
    """

    def __init__(
        self,
        adapters: list["BaseAdapter"],
        cache: Optional["CacheRepository"] = None,
        use_cache: bool = True,
        rotator: Optional["SiteRotator"] = None,
        quota: Optional["DailyQuotaTracker"] = None,
        parser: Optional["StandardParser"] = None,
        site_order: Optional[list[str]] = None,
        query_interval: Optional[tuple[float, float]] = None,
        quota_tracker: Optional["DailyQuotaTracker"] = None,
    ) -> None:
        # 1.初始化基类（创建_核心容器）
        super().__init__(
            adapters=adapters,
            cache=cache,
            use_cache=use_cache,
            rotator=rotator,
            quota=quota_tracker or quota,
            parser=parser,
            site_order=site_order,
            query_interval=query_interval,
        )
        self.quota_tracker = quota_tracker

        # 2.创建所有（依赖注入）
        self._routing = RoutingHandler(self._core)
        self._single = SingleQueryHandler(self._core, self._routing)
        self._csres = CsresHandler(self._core)
        self._mini_bucket = MiniBucketHandler(self._core, self._routing, self._single)
        self._overflow = OverflowHandler(self._core, self._routing)
        self._report = ReportHandler(self._core)
        self._batch = BatchHandler(
            core=self._core,
            routing=self._routing,
            single=self._single,
            csres=self._csres,
            mini_bucket=self._mini_bucket,
            overflow=self._overflow,
            report=self._report,
        )

    # ===== 批量查询入口 =====

    def query_standards(
        self,
        items: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        use_parallel: Optional[bool] = None,
        force_refresh: bool = False,
        preferred_site: str | None = None,
    ) -> List[QueryResult]:
        """统一查询入口：所有端（CLI/Web/WinUI）均通过此方法查询。"""
        return self._batch.query_standards(
            items=items,
            progress_callback=progress_callback,
            result_callback=result_callback,
            use_parallel=use_parallel,
            force_refresh=force_refresh,
            preferred_site=preferred_site,
        )

    def query_batch_parsed(
        self,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        preferred_site: str | None = None,
    ) -> List[QueryResult]:
        """[已废弃] 使用 query_standards(items, use_parallel=True) 替代。"""
        return self._batch.query_batch_parsed(
            parsed_list=parsed_list,
            progress_callback=progress_callback,
            result_callback=result_callback,
            preferred_site=preferred_site,
        )

    # ===== 路由/配额方法 =====

    def _bucket_key(self, logical_code: str, preferred_site: str | None = None) -> str:
        """按站点确定桶标识（委托给 RoutingHandler）。"""
        return self._routing._bucket_key(logical_code, preferred_site)

    def _resolve_base_route(self, logical_code: str) -> list[str]:
        """按标准代号确定基础路由链（委托给 RoutingHandler）。"""
        return self._routing._resolve_base_route(logical_code)

    def _build_chain_for_item(
        self, item: Tuple[str, int, int, str, Optional[int], str], preferred_site: str | None = None
    ) -> list[str]:
        """返回条目对应的完整优先级链。"""
        return self._routing._build_chain_for_item(item, preferred_site)

    def _build_mini_buckets(self, bucket_items: list, chain: list, weights: Any) -> list[tuple[str, list]]:
        """按权重或轮询将桶内条目拆分为 50 条小桶。"""
        return self._mini_bucket._build_mini_buckets(bucket_items, chain, weights)

    def _run_mini_bucket_queries(
        self, mini_buckets: list, chain: list, primary_site: str, ctx: dict, skip_overflow: bool = False
    ) -> list:
        """错峰执行小桶查询，冷却/配额感知，返回溢出条目列表。"""
        return self._mini_bucket._run_mini_bucket_queries(mini_buckets, chain, primary_site, ctx, skip_overflow)

    def get_quota_info(self) -> dict[str, int]:
        """返回各站点配额信息。"""
        return self._routing.get_quota_info()

    def get_all_sites(self) -> List[str]:
        """返回所有已注册站点名称。"""
        return self._routing.get_all_sites()

    def get_adapter(self, name: str) -> Optional["BaseAdapter"]:
        """获取指定站点适配器。"""
        return self._routing.get_adapter(name)

    def get_site_cooldown(self, name: str) -> float:
        """返回指定站点剩余冷却秒数。"""
        return self._routing.get_site_cooldown(name)

    def plan_batch(self, total: int, logical_code: str = "") -> List[Tuple[str, int]]:
        """按配额预估分配方案。"""
        return self._routing.plan_batch(total, logical_code)

    # ===== 状态查询方法 =====

    def get_query_status(self) -> dict[str, bool | int]:
        """返回查询引擎运行时状态。"""
        return {
            "is_running": self._core.query_active,
            "overflow_count": self._core.overflow_item_count,
            "csres_active": self._core.csres_active,
            "is_idle": not self._core.query_active,
        }

    def get_csres_status(self) -> dict[str, Any]:
        """返回 CSRES 线程状态。"""
        return {
            "is_active": self._core.csres_active,
            "processed": self._core.csres_processed,
            "total": self._core.csres_total,
        }

    def get_overflow_count(self) -> int:
        """返回溢出条目计数。"""
        return self._core.overflow_item_count

    def is_idle(self) -> bool:
        """查询引擎是否空闲。"""
        return not self._core.query_active

    def is_query_running(self) -> bool:
        """查询引擎是否正在运行。"""
        return self._core.query_active

    # ===== 暂停/恢复 =====

    def set_pause_event(self, event: Any) -> None:
        """设置暂停事件，透传至各查询路径供循环检查。"""
        self._core.pause_event = event

    # ===== 向后兼容属性代理 =====

    @property
    def use_cache(self) -> bool:
        return self._core.use_cache

    @property
    def cache(self):
        return self._core.cache

    @property
    def rotator(self):
        return self._core.rotator

    @property
    def quota(self):
        return self._core.quota


__all__ = [
    "QueryEngine",
    "QueryEngineCore",
    "EngineCore",
    "RoutingHandler",
    "SingleQueryHandler",
    "BatchHandler",
    "CsresHandler",
    "MiniBucketHandler",
    "OverflowHandler",
    "ReportHandler",
    "PROGRESS_TAG",
    "CODE_ROUTES",
    "_DEFAULT_FALLBACK_CHAIN",
]
