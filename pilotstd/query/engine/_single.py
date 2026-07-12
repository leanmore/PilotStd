# pilotstd/query/engine/_single.py
"""单条查询处理器 — 缓存优先 + 适配器优先级链 + 配额感知。

组合模式重构：SingleMixin → SingleQueryHandler，依赖通过 EngineCore 注入。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

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
        """单条查询内核：缓存优先 + 适配器优先级链 + 配额感知。"""
        part_str = f".{part}" if part else ""
        target = f"{logical_code} {number}{part_str}-{year}"

        cache = self._core.cache
        adapters = self._core.adapters
        use_cache = self._core.use_cache
        if use_cache and not force_refresh and not preferred_site:
            for adapter in adapters:
                if cache is not None:
                    cached = cache.get(target, adapter.site_name)
                if cached:
                    logger.debug("查询 [%s] 缓存命中 @%s", target, cached.source_site)
                    return cached

        priority = self._routing._get_priority(logical_code, preferred_site)
        rotator = self._core.rotator
        if rotator and not priority:
            logger.warning("所有站点均在冷却中，等待恢复...")
            rotator.wait_for_any_recovery([a.site_name for a in adapters])
            priority = self._routing._get_priority(logical_code, preferred_site)
            logger.info("站点冷却恢复，继续查询")

        logger.debug("查询 [%s] 路由=%s", target, "→".join(priority) if priority else "(全部冷却)")
        adapter_map = self._core.adapter_map
        quota = self._core.quota
        quota_exhausted = True
        tried: list[str] = []
        for name in priority:
            adp: BaseAdapter | None = adapter_map.get(name)
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
                return result

        if quota_exhausted:
            logger.info("查询 [%s] ✗配额耗尽", target)
            return QueryResult(
                standard_number=target,
                error_message="所有站点今日配额已用尽，请明日再试",
                source_site="",
            )

        logger.info("查询 [%s] ✗ tried=%s", target, "→".join(tried))
        return QueryResult(
            standard_number=target,
            error_message="所有来源均未找到该标准",
            source_site="",
        )

    def _verify_adoption(self, result: QueryResult) -> QueryResult:
        """采标检测：判断是否为采标标准，采标标准不可直接下载。"""
        if not result.is_adopted and "采标" in result.status:
            result.is_adopted = True
        result.is_downloadable = not result.is_adopted
        return result
