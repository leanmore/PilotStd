# pilotstd/query/engine/_single.py
# 查询引擎单条查询混入模块
"""单条查询内核：缓存优先 + 适配器优先级链 + 配额感知。"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..models import QueryResult

logger = logging.getLogger(__name__)


class SingleMixin:
    """单条查询混入类 — _query_one + _verify_adoption。"""

    _use_cache: Any
    _adapters: Any
    _cache: Any
    _rotator: Any
    _adapter_map: Any
    _quota: Any
    _record: Any

    def _query_one(
        self,
        logical_code: str,
        number: int,
        year: int,
        std_name: str = "",
        part: Optional[int] = None,
        force_refresh: bool = False,
        num_prefix: str = "",
        preferred_site: str = "",
    ) -> QueryResult:
        """单条查询内核：缓存优先 + 适配器优先级链 + 配额感知。"""
        part_str = f".{part}" if part else ""
        target = f"{logical_code} {number}{part_str}-{year}"
        if self._use_cache and not force_refresh:
            for adapter in self._adapters:
                cached = self._cache.get(target, adapter.site_name)
                if cached:
                    logger.debug("查询 [%s] 缓存命中 @%s", target, cached.source_site)
                    return cached

        priority = self._get_priority(logical_code, preferred_site)
        if self._rotator and not priority:
            logger.warning("所有站点均在冷却中，等待恢复...")
            self._rotator.wait_for_any_recovery([a.site_name for a in self._adapters])
            priority = self._get_priority(logical_code, preferred_site)
            logger.info("站点冷却恢复，继续查询")
        logger.debug("查询 [%s] 路由=%s", target, "→".join(priority) if priority else "(全部冷却)")

        quota_exhausted = True
        tried: list[str] = []
        for name in priority:
            adapter = self._adapter_map.get(name)
            if adapter is None:
                continue
            if self._quota and self._quota.get_search_remaining(name) <= 0:
                logger.warning("%s(%s) 今日配额已用尽，跳过", adapter.site_label, name)
                continue
            quota_exhausted = False
            tried.append(name)
            result = adapter.query_with_strategy(logical_code, number, year, std_name, part, num_prefix=num_prefix)
            if result and result.is_found():
                result.source_site = adapter.site_name
                if not result.standard_number:
                    result.standard_number = target
                result = self._verify_adoption(result)
                if getattr(result, "match_status", "") == "exact":
                    self._cache.put(result)
                self._record(name, 1)
                logger.info("查询 [%s] ✓%s(%s) tried=%s", target, name, result.match_status, "→".join(tried))
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
