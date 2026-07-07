# pilotstd/query/engine/_core.py
# 查询引擎核心类 — 构造函数 + 状态查询方法 + 配额记录
"""QueryEngine 核心：初始化、运行时状态、配额记录。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..adapters.base import BaseAdapter
from ..cache import CacheRepository
from ..daily_quota import DailyQuotaTracker
from ..rotator import SiteRotator

logger = logging.getLogger(__name__)


class QueryEngineCore:
    """查询引擎核心：适配器管理、缓存开关、站点轮转、配额追踪。"""

    def __init__(
        self,
        adapters: List[BaseAdapter],
        cache: CacheRepository,
        use_cache: bool = True,
        rotator: Optional[SiteRotator] = None,
        quota_tracker: Optional[DailyQuotaTracker] = None,
        site_order: Optional[List[str]] = None,
        query_interval: Optional[tuple[float, float]] = None,
        parser: Optional[Any] = None,
    ):
        self._adapters = adapters
        # site_name → adapter 映射，O(1) 查找
        self._adapter_map: Dict[str, BaseAdapter] = {a.site_name: a for a in adapters}
        self._cache = cache
        self._use_cache = use_cache
        self._rotator = rotator  # 站点轮转（冷却管理）
        self.rotator = rotator  # 公开引用，供外部（如测试）查询冷却状态
        self._quota = quota_tracker  # 每日配额
        self._site_order = site_order  # 用户自定义优先级
        self._parser = parser  # StandardParser 实例，query_batch 解析用
        # 查询间隔（含随机抖动）：(最小秒, 最大秒)，如 (0.5, 1.5)。None=不启用
        self._query_interval = query_interval
        # 查询运行时状态（供进度条和外部监控查询）
        self._query_active = False
        self._overflow_item_count = 0
        self._csres_active = False
        self._csres_processed = 0
        self._csres_total = 0
        # 暂停事件：由 Worker 层传入，Engine 在串行循环中检查
        self._pause_event: Optional[Any] = None

    def set_pause_event(self, event: Optional[Any]) -> None:
        """设置暂停事件（由 Manager 从 Worker 层传入）。"""
        self._pause_event = event

    # ════════════════════════════════════════════════════════════════
    # 公共 API
    # ════════════════════════════════════════════════════════════════

    def is_query_running(self) -> bool:
        """查询引擎是否正在执行批量查询。"""
        return self._query_active

    def get_overflow_count(self) -> int:
        """当前溢出队列中待重试的条目数。"""
        return self._overflow_item_count

    def get_csres_status(self) -> dict[str, Any]:
        """返回 CSRES 线程状态。"""
        return {
            "is_active": self._csres_active,
            "processed": self._csres_processed,
            "total": self._csres_total,
            "remaining": max(0, self._csres_total - self._csres_processed),
        }

    def is_idle(self) -> bool:
        """查询引擎是否完全空闲（无查询、无溢出、CSRES 已结束）。"""
        return not self._query_active and self._overflow_item_count == 0 and not self._csres_active

    # ════════════════════════════════════════════════════════════════
    # 配额 / 轮转记录
    # ════════════════════════════════════════════════════════════════

    def _record(self, site_name: str, count: int) -> None:
        """记录配额消耗 + 通知站点轮转器记录成功请求。"""
        if self._quota:
            self._quota.record_usage(site_name, count)
        if self._rotator:
            for _ in range(count):
                self._rotator.record_success(site_name)
