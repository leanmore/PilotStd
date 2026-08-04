# 模块：pilotstd/query/engine/_core_types.py
"""EngineCore 依赖容器 — 查询引擎组合模式重构。

替代 Mixin 通过 MRO 隐式访问属性。所有持久依赖和运行时状态集中管理，
由 QueryEngine 持有并注入各 Handler。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ...scan.parser import StandardParser
    from ..adapters.base import BaseAdapter
    from ..cache import CacheRepository
    from ..daily_quota import DailyQuotaTracker
    from ..rotator import SiteRotator


@dataclass
class EngineCore:
    """查询引擎依赖容器 — 组合模式替代 MRO 隐式属性访问。"""

    # ---- 适配器 ----
    adapters: list[BaseAdapter] = field(default_factory=list)
    adapter_map: dict[str, BaseAdapter] = field(default_factory=dict)

    # ---- 缓存与路由 ----
    cache: Optional[CacheRepository] = None
    rotator: Optional[SiteRotator] = None
    quota: Optional[DailyQuotaTracker] = None

    # ---- 配置 ----
    use_cache: bool = True
    site_order: Optional[list[str]] = None
    parser: Optional[StandardParser] = None
    query_interval: Optional[tuple[float, float]] = None

    # ---- 运行时状态 ----
    pause_event: Optional[Any] = None
    query_active: bool = False
    csres_active: bool = False
    csres_processed: int = 0
    csres_total: int = 0
    overflow_item_count: int = 0

    # ---- 方法 ----

    def record(self, site_name: str, count: int = 1) -> None:
        """记录站点查询成功次数（配额消耗 + 轮转统计）。"""
        if self.quota:
            self.quota.record_usage(site_name, count)
        if self.rotator:
            for _ in range(count):
                self.rotator.record_success(site_name)

    def is_idle(self) -> bool:
        """查询引擎是否完全空闲。"""
        return not self.query_active and self.overflow_item_count == 0 and not self.csres_active

    def get_csres_status(self) -> dict[str, Any]:
        """返回 CSRES 线程状态。"""
        return {
            "is_active": self.csres_active,
            "processed": self.csres_processed,
            "total": self.csres_total,
            "remaining": max(0, self.csres_total - self.csres_processed),
        }
