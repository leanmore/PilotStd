# pilotstd/query/engine/_single.py
"""单条查询处理器 — 缓存优先 + 适配器优先级链 + 配额感知。

组合模式重构：SingleMixin → SingleQueryHandler，依赖通过 EngineCore 注入。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from ..models import QueryResult

if TYPE_CHECKING:
    from ..adapters.base import BaseAdapter
    from ._core_types import EngineCore
    from ._routing import RoutingHandler

logger = logging.getLogger(__name__)


class SingleQueryHandler:
    """单条查询处理器 — 替代原 SingleMixin。

    依赖 RoutingHandler 获取优先级链，通过 EngineCore 访问缓存/适配器/配额。
    """

    def __init__(self, core: "EngineCore", routing: "RoutingHandler") -> None:
        self._core = core
        self._routing = routing

    # ── 5 步搜索链路（从 _query_one 提取） ──

    def _step_cache_lookup(
        self,
        target: str,
        adapters: list["BaseAdapter"],
        cache: Any,
        use_cache: bool,
        force_refresh: bool,
        preferred_site: str | None = None,
    ) -> QueryResult | None:
        """Step 1：遍历各适配器缓存，命中则返回 QueryResult，否则返回 None。"""
        if not use_cache or force_refresh or preferred_site:
            return None
        for adapter in adapters:
            cached = None
            if cache is not None:
                cached = cache.get(target, adapter.site_name)
            if cached:
                logger.debug("查询 [%s] 缓存命中 @%s", target, cached.source_site)
                return cached
        return None

    def _step_get_priority_chain(
        self,
        logical_code: str,
        preferred_site: str | None,
        adapters: list["BaseAdapter"],
        rotator: Any,
    ) -> list[str]:
        """Step 2：获取适配器优先级链；全部冷却时阻塞等待恢复后重试。"""
        priority = self._routing._get_priority(logical_code, preferred_site)
        if rotator and not priority:
            logger.warning("所有站点均在冷却中，等待恢复...")
            rotator.wait_for_any_recovery([a.site_name for a in adapters])
            priority = self._routing._get_priority(logical_code, preferred_site)
            logger.info("站点冷却恢复，继续查询")
        return priority

    def _step_query_adapters(
        self,
        target: str,
        logical_code: str,
        number: int,
        year: int,
        std_name: str,
        part: int | None,
        num_prefix: str,
        priority: list[str],
        adapter_map: dict[str, "BaseAdapter"],
        quota: Any,
        cache: Any,
    ) -> tuple[QueryResult | None, list[str], bool]:
        """Step 3：按优先级链逐适配器查询。

        Returns:
            (result | None, tried_sites, quota_exhausted)
            - result: 查询命中时返回 QueryResult，否则 None
            - tried_sites: 实际尝试过的站点名列表
            - quota_exhausted: 是否因全部站点配额耗尽而退出
        """
        quota_exhausted = True
        tried: list[str] = []
        for name in priority:
            adp = adapter_map.get(name)
            if adp is None:
                continue
            if quota and quota.get_search_remaining(name) <= 0:
                logger.warning("%s(%s) 今日配额已用尽，跳过", adp.site_label, name)
                continue
            quota_exhausted = False
            tried.append(name)
            result = adp.query_with_strategy(logical_code, number, year, std_name, part, num_prefix=num_prefix)
            if result and result.is_found():
                result.source_site = adp.site_name
                if not result.standard_number:
                    result.standard_number = target
                result = self._verify_adoption(result)
                if getattr(result, "match_status", "") == "exact" and cache is not None:
                    cache.put(result)
                self._core.record(name, 1)
                logger.info(
                    "查询 [%s] ✓%s(%s) tried=%s",
                    target,
                    name,
                    result.match_status,
                    "→".join(tried),
                )
                return result, tried, False
        return None, tried, quota_exhausted

    @staticmethod
    def _step_quota_exhausted(target: str) -> QueryResult:
        """Step 4：配额耗尽兜底 — 所有站点今日配额已用尽。"""
        return QueryResult(
            standard_number=target,
            error_message="所有站点今日配额已用尽，请明日再试",
            source_site="",
        )

    @staticmethod
    def _step_not_found(target: str, tried: list[str]) -> QueryResult:
        """Step 5：未找到兜底 — 所有来源均未匹配到该标准。"""
        return QueryResult(
            standard_number=target,
            error_message="所有来源均未找到该标准",
            source_site="",
        )

    # ── 编排方法 ──

    def _query_one(
        self,
        logical_code: str,
        number: int,
        year: int,
        std_name: str = "",
        part: Optional[int] = None,
        force_refresh: bool = False,
        num_prefix: str = "",
        preferred_site: str | None = None,
    ) -> QueryResult:
        """单条查询内核：缓存优先 + 适配器优先级链 + 配额感知。

        内部编排 5 步搜索链路，每步已提取为独立可测方法。
        """
        part_str = f".{part}" if part else ""
        target = f"{logical_code} {number}{part_str}-{year}"

        # Step 1: 缓存查找
        cached = self._step_cache_lookup(
            target=target,
            adapters=self._core.adapters,
            cache=self._core.cache,
            use_cache=self._core.use_cache,
            force_refresh=force_refresh,
            preferred_site=preferred_site,
        )
        if cached is not None:
            return cached

        # Step 2: 获取适配器优先级链
        priority = self._step_get_priority_chain(
            logical_code=logical_code,
            preferred_site=preferred_site,
            adapters=self._core.adapters,
            rotator=self._core.rotator,
        )

        logger.debug("查询 [%s] 路由=%s", target, "→".join(priority) if priority else "(全部冷却)")

        # Step 3: 逐适配器查询
        result, tried, quota_exhausted = self._step_query_adapters(
            target=target,
            logical_code=logical_code,
            number=number,
            year=year,
            std_name=std_name,
            part=part,
            num_prefix=num_prefix,
            priority=priority,
            adapter_map=self._core.adapter_map,
            quota=self._core.quota,
            cache=self._core.cache,
        )
        if result is not None:
            return result

        # Step 4: 配额耗尽兜底
        if quota_exhausted:
            logger.info("查询 [%s] ✗配额耗尽", target)
            return self._step_quota_exhausted(target)

        # Step 5: 未找到兜底
        logger.info("查询 [%s] ✗ tried=%s", target, "→".join(tried))
        return self._step_not_found(target, tried)

    def _verify_adoption(self, result: QueryResult) -> QueryResult:
        """采标检测：判断是否为采标标准，采标标准不可直接下载。"""
        if not result.is_adopted and "采标" in result.status:
            result.is_adopted = True
        result.is_downloadable = not result.is_adopted
        return result
