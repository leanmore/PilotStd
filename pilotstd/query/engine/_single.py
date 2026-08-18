# 模块：项目/查询/引擎/_脚本
"""单条查询处理器 — 缓存优先 + 适配器优先级链 + 配额感知。

组合模式重构：SingleMixin → SingleQueryHandler，依赖通过 EngineCore 注入。
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any, Optional

from ..models import QueryResult
from ..routing.router_v2 import AllRoutesExhaustedException, get_routing_service, is_v2_enabled
from ..routing.router_v2_metrics import build_decision, record_decision, record_v1_brief

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

    # ──5步搜索链路（从_查询_提取）──

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
        rotator: Any = None,
        metrics: Any = None,
    ) -> tuple[QueryResult | None, list[str], bool]:
        """Step 3：按优先级链逐适配器查询。

        增加运行时冷却检查，防止 _get_priority 返回后到实际查询前
        站点进入冷却导致的无效请求。

        Returns:
            (result | None, tried_sites, quota_exhausted)
        """
        quota_exhausted = True
        tried: list[str] = []
        for name in priority:
            adp = adapter_map.get(name)
            if adp is None:
                continue
            # ✅#460:运行时冷却检查（__返回后到实际查询前的窗口）
            if rotator and rotator.get_cooldown_remaining(name) > 0:
                logger.debug("[RUNTIME_COOLDOWN] 跳过=%s 原因=运行时冷却", name)
                if metrics:
                    metrics.increment("site_cooling")
                continue
            if quota and quota.get_search_remaining(name) <= 0:
                logger.warning("%s(%s) 今日配额已用尽，跳过", adp.site_label, name)
                if metrics:
                    metrics.increment("quota_exhausted")  # ✅ #46 P1
                continue
            quota_exhausted = False
            tried.append(name)
            # 阶段3.1:_执行层落地（单条查询路径）
            if rotator and name in rotator._sites:
                _interval = rotator._sites[name].request_interval
                if _interval > 0 and os.environ.get("PYTEST_RUNNING") != "1":
                    import time as _time

                    _time.sleep(_interval)
                    if metrics:
                        metrics.increment("request_interval_wait", count=int(_interval * 1000))  # 毫秒累加
            result = adp.query_with_strategy(logical_code, number, year, std_name, part, num_prefix=num_prefix)
            if result and result.is_found():
                result.source_site = adp.site_name
                if not result.standard_number:
                    result.standard_number = target
                result = self._verify_adoption(result)
                if getattr(result, "match_status", "") == "exact" and cache is not None:
                    cache.put(result)
                self._core.record(name, 1)
                if metrics:
                    metrics.increment("matched")  # ✅ #46 P1: 原子单元埋点
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

        # 步骤1:缓存查找
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

        # v2 灰度分支：RouteChain 链式降级（未指定站点时启用）
        if is_v2_enabled() and not preferred_site:
            try:
                return self._query_one_v2(target, logical_code, number, year, std_name, part, num_prefix)
            except AllRoutesExhaustedException as exc:
                logger.info("查询 [%s] ✗%s", target, exc)
                return QueryResult(standard_number=target, error_message=str(exc), source_site="")

        # v1 精简对比日志计时（用于 4.4 回归对比）
        _v1_t0 = time.time()

        # 步骤2:获取适配器优先级链
        priority = self._step_get_priority_chain(
            logical_code=logical_code,
            preferred_site=preferred_site,
            adapters=self._core.adapters,
            rotator=self._core.rotator,
        )

        logger.debug("查询 [%s] 路由=%s", target, "→".join(priority) if priority else "(全部冷却)")

        # 步骤3:逐适配器查询（含运行时冷却检查）
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
            rotator=self._core.rotator,  # ✅ #46 P0: 运行时冷却检查
            metrics=getattr(self._core, "metrics", None),
        )
        if result is not None:
            record_v1_brief(target, getattr(result, "source_site", None), (time.time() - _v1_t0) * 1000)
            return result

        # 步骤4:配额耗尽兜底
        if quota_exhausted:
            logger.info("查询 [%s] ✗配额耗尽", target)
            record_v1_brief(target, None, (time.time() - _v1_t0) * 1000)
            return self._step_quota_exhausted(target)

        # 步骤5:未找到兜底
        logger.info("查询 [%s] ✗ tried=%s", target, "→".join(tried))
        record_v1_brief(target, None, (time.time() - _v1_t0) * 1000)
        return self._step_not_found(target, tried)

    def _query_one_v2(
        self,
        target: str,
        logical_code: str,
        number: int,
        year: int,
        std_name: str,
        part: int | None,
        num_prefix: str,
    ) -> QueryResult:
        """v2 执行路径：遍历 RouteChain 实现链式降级 + 批次配额扣减。

        单个站点失败或返回空结果时自动尝试链上下一个站点；
        链上所有站点均失败则抛 AllRoutesExhaustedException（由 _query_one 捕获转错误结果）。
        """
        routing_service = get_routing_service()
        chain = routing_service.get_route_chain(target)
        intent = routing_service.parser.parse(target)
        _t0 = time.time()

        logger.debug("[v2 Router] 查询 [%s] 路由=%s", target, "→".join(chain.sites) if chain.sites else "(空)")

        tried: list[str] = []
        quota_skipped: list[str] = []
        for site_id in chain.sites:
            # 请求前扣减批次配额，配额耗尽则跳过该站
            if not routing_service.consume_quota(site_id):
                logger.info("[v2 Router] %s quota exhausted, skipping.", site_id)
                quota_skipped.append(site_id)
                continue
            adp = self._core.adapter_map.get(site_id)
            if adp is None:
                continue
            tried.append(site_id)
            try:
                result = adp.query_with_strategy(logical_code, number, year, std_name, part, num_prefix=num_prefix)
                if result and result.is_found():
                    result.source_site = adp.site_name
                    if not result.standard_number:
                        result.standard_number = target
                    result = self._verify_adoption(result)
                    self._core.record(site_id, 1)
                    logger.info(
                        "[v2 Router] Hit on %s (%s) tried=%s",
                        site_id,
                        result.match_status,
                        "→".join(tried),
                    )
                    record_decision(
                        build_decision(
                            target,
                            intent,
                            chain.sites,
                            tried,
                            site_id,
                            len(tried) - 1,
                            quota_skipped,
                            (time.time() - _t0) * 1000,
                        )
                    )
                    return result
            except Exception as exc:
                # 单站异常不阻断整体，记录后继续尝试下一站
                logger.warning("[v2 Router] %s failed: %s, trying next.", site_id, exc)
                continue

        record_decision(
            build_decision(
                target, intent, chain.sites, tried, None, len(tried), quota_skipped, (time.time() - _t0) * 1000
            )
        )
        raise AllRoutesExhaustedException(
            f"查询 '{target}' 链上所有站点均失败，已尝试：{'→'.join(tried) if tried else '(无)'}"
        )

    def _verify_adoption(self, result: QueryResult) -> QueryResult:
        """采标检测：判断是否为采标标准，采标标准不可直接下载。"""
        if not result.is_adopted and "采标" in result.status:
            result.is_adopted = True
        result.is_downloadable = not result.is_adopted
        return result
