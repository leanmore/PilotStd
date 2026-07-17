# pilotstd/query/engine/_core.py
# mypy: disable-error-code="no-any-return"
"""查询引擎核心基类 — 组合模式重构，提供 EngineCore 容器和状态查询。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...scan.parser import StandardParser
    from ..adapters.base import BaseAdapter
    from ..cache import CacheRepository
    from ..daily_quota import DailyQuotaTracker
    from ..rotator import SiteRotator

from ._core_types import EngineCore

logger = logging.getLogger(__name__)


class QueryEngineCore:
    """查询引擎核心基类 — 持有 EngineCore 容器，提供状态查询和记录方法。

    组合模式重构后，不再通过 MRO 隐式传递属性，所有依赖显式存储在 _core 中。
    子类（QueryEngine）通过组合 Handler 而非继承 Mixin 来获得功能。
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
    ) -> None:
        """初始化 EngineCore 容器。"""
        adapter_map = {a.site_name: a for a in adapters}

        self._core = EngineCore(
            adapters=adapters,
            adapter_map=adapter_map,
            cache=cache,
            rotator=rotator,
            quota=quota,
            use_cache=use_cache,
            site_order=site_order,
            parser=parser,
            query_interval=query_interval,
            pause_event=None,
            query_active=False,
            csres_active=False,
            csres_processed=0,
            csres_total=0,
            overflow_item_count=0,
        )

    # ===== 属性代理（供 Handler 访问） =====

    @property
    def core(self) -> EngineCore:
        return self._core

    @property
    def adapters(self) -> list["BaseAdapter"]:
        return self._core.adapters

    @property
    def adapter_map(self) -> dict[str, "BaseAdapter"]:
        return self._core.adapter_map

    @property
    def cache(self):
        return self._core.cache

    @property
    def rotator(self):
        return self._core.rotator

    @property
    def quota(self):
        return self._core.quota

    @property
    def use_cache(self) -> bool:
        return self._core.use_cache

    @property
    def site_order(self):
        return self._core.site_order

    @property
    def parser(self):
        return self._core.parser

    @property
    def query_interval(self):
        return self._core.query_interval

    @property
    def pause_event(self):
        return self._core.pause_event

    @pause_event.setter
    def pause_event(self, value):
        self._core.pause_event = value

    # ===== 状态查询方法 =====

    def is_idle(self) -> bool:
        return not self._core.query_active

    def is_query_running(self) -> bool:
        return self._core.query_active

    def get_csres_status(self) -> dict[str, Any]:
        """返回 CSRES 后台查询的当前状态快照，供 UI 轮询展示。"""
        return {
            "is_active": self._core.csres_active,
            "processed": self._core.csres_processed,
            "total": self._core.csres_total,
        }

    def get_overflow_count(self) -> int:
        return self._core.overflow_item_count

    def _record(self, site_name: str, count: int = 1) -> None:
        """记录站点查询成功次数（供 Mixin/Handler 使用）。"""
        self._core.record(site_name, count)
