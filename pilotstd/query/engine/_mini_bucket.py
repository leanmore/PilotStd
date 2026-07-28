# pilotstd/query/engine/_mini_bucket.py
"""小桶构建与逐桶查询执行处理器 — 替代原 MiniBucketMixin。

组合模式重构：MiniBucketMixin → MiniBucketHandler，依赖通过 EngineCore 注入。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from ..search_strategy import MATCH_SCORE

if TYPE_CHECKING:
    from ._core_types import EngineCore
    from ._routing import RoutingHandler
    from ._single import SingleQueryHandler

logger = logging.getLogger(__name__)


# Phase 3.1: request_interval 执行层辅助函数（提取以降低 _process_single_query 圈复杂度）
def _apply_request_interval(rotator: Any, site_name: str, ctx: dict) -> None:
    """从 SiteState 读取 request_interval 并 time.sleep，记录到 metrics。"""
    if rotator and site_name in rotator._sites:
        interval = rotator._sites[site_name].request_interval
        if interval > 0:
            time.sleep(interval)
            m = ctx.get("metrics")
            if m:
                m.increment("request_interval_wait", count=int(interval * 1000))


class MiniBucketHandler:
    """小桶处理器 — 小桶拆分 + 逐桶查询执行。

    替代原 MiniBucketMixin，依赖通过 EngineCore 访问。
    """

    _MINI_BUCKET_SIZE = 50  # 每个小桶最多 50 条，控制单次查询粒度
    _MINI_BUCKET_STAGGER = 5  # 小桶间错峰间隔（秒），防止惊群效应

    def __init__(
        self,
        core: "EngineCore",
        routing: "RoutingHandler",
        single: "SingleQueryHandler",
    ) -> None:
        self._core = core
        self._routing = routing
        self._single = single

    # ── 小桶构建 ──

    def _build_mini_buckets(
        self,
        bucket_items: list,
        chain: list,
        weights: Any,
    ) -> list[tuple[str, list]]:
        """按权重或轮询将桶内条目拆分为 50 条小桶。"""
        rotator = self._core.rotator

        if weights and len(weights) == len(chain):
            weights = cast(list[int], weights)
            # 检测冷却中的站点，将其权重重新分配给活跃站点
            cooled_sites: set[str] = set()
            if rotator:
                for site in chain:
                    if rotator.get_cooldown_remaining(site) > 0:
                        cooled_sites.add(site)

            active_weights = list(weights)
            if cooled_sites:
                cooled_w = sum(w for w, s in zip(weights, chain) if s in cooled_sites)
                active_total = sum(w for w, s in zip(weights, chain) if s not in cooled_sites)
                if active_total > 0:
                    active_weights = [
                        0 if s in cooled_sites else w + round(cooled_w * w / active_total)
                        for w, s in zip(weights, chain)
                    ]
                    logger.info(
                        "[MINI_BUCKET] 冷却站点=%s 重分配权重=%s",
                        ",".join(sorted(cooled_sites)),
                        active_weights,
                    )

            total_w = sum(active_weights)
            mini_buckets: list[tuple[str, list]] = []
            start = 0
            for i, site in enumerate(chain):
                if site in cooled_sites:
                    continue
                if i == len(chain) - 1:
                    # 最后一个站点拿走所有剩余条目
                    target = len(bucket_items) - start
                else:
                    target = round(len(bucket_items) * active_weights[i] / total_w)
                end = min(start + target, len(bucket_items))
                if end > start:
                    site_slice = bucket_items[start:end]
                    start = end
                    for j in range(0, len(site_slice), self._MINI_BUCKET_SIZE):
                        mini_buckets.append((site, site_slice[j : j + self._MINI_BUCKET_SIZE]))
            if start < len(bucket_items):
                remaining = bucket_items[start:]
                for s in chain:
                    if s not in cooled_sites:
                        mini_buckets.append((s, remaining))
                        break
                else:
                    mini_buckets.append((chain[0], remaining))
            return mini_buckets

        # 轮询分配
        mini_buckets = []
        for i in range(0, len(bucket_items), self._MINI_BUCKET_SIZE):
            mb = bucket_items[i : i + self._MINI_BUCKET_SIZE]
            site = chain[(i // self._MINI_BUCKET_SIZE) % len(chain)]
            mini_buckets.append((site, mb))
        return mini_buckets

    # ── 单条查询处理 ──

    def _process_single_query(
        self,
        idx: int,
        item: tuple,
        assigned_site: str,
        adapter: Any,
        ctx: dict,
        primary_site: str,
        overflow_items: list,
        skip_overflow: bool = False,
    ) -> None:
        """处理单个条目的查询：执行 → 结果记录 → 缓存 → 回调。
        原地修改 overflow_items 和 ctx（results/item_chains/overflow_events等）。"""
        rotator = self._core.rotator
        if rotator and rotator.get_cooldown_remaining(assigned_site) > 0:
            if not skip_overflow:
                overflow_items.append((idx, item))
            return

        try:
            _t0 = time.time()
            # Phase 3.1: request_interval 执行层落地
            _apply_request_interval(rotator, assigned_site, ctx)
            result = adapter.query_with_strategy(item[0], item[1], item[2], item[3], item[4])
            _elapsed = round(time.time() - _t0, 3)
            if rotator:
                rotator.record_query_result(
                    assigned_site,
                    result is not None and result.is_found(),
                    _elapsed,
                )
        except Exception:
            ctx["item_chains"].setdefault(idx, []).append(assigned_site)
            logger.warning("查询 [%s %s-%s] 异常 @%s", item[0], item[1], item[2], assigned_site)
            # ✅ #46 P1: parse_failed 计数器（异常类解析失败）
            m = ctx.get("metrics")
            if m:
                m.increment("parse_failed")
            if not skip_overflow:
                overflow_items.append((idx, item))
            return

        target_display = f"{item[0]} {item[1]}-{item[2]}"
        if result:
            result.source_site = assigned_site
            self._core.record(assigned_site, 1)
            ctx["_record_usage"](assigned_site)
            ctx["_record_match"](assigned_site, getattr(result, "match_status", "err"))
            score = MATCH_SCORE.get(getattr(result, "match_status", ""), 0)
            ctx["item_chains"].setdefault(idx, []).append(assigned_site)

            if score >= 100:
                ctx["results"][idx] = result
                with ctx["_prog_lock"]:
                    ctx["_prog_ok"][0] += 1
                logger.info(
                    "查询 [%s] [OK]%s(%s)",
                    target_display,
                    assigned_site,
                    getattr(result, "match_status", ""),
                )
                cache = self._core.cache
                if cache:
                    cache.put(result)
                    logger.info("[CACHE] put exact match: %s → %s", target_display, assigned_site)
                if ctx["result_callback"] and result.is_found():
                    ctx["result_callback"](idx, result)
                ctx["bump"]()
            else:
                logger.info(
                    "查询 [%s] [LO]%s(%s=%d) 未达100分回池",
                    target_display,
                    assigned_site,
                    getattr(result, "match_status", ""),
                    score,
                )
                ctx["overflow_events"].append((time.time(), primary_site, assigned_site, idx))
                if not skip_overflow:
                    overflow_items.append((idx, item))
        else:
            ctx["item_chains"].setdefault(idx, []).append(assigned_site)
            chain_str = "→".join(ctx["item_chains"].get(idx, []))
            logger.info("查询 [%s] [NG]%s tried=%s", target_display, assigned_site, chain_str)
            if not skip_overflow:
                overflow_items.append((idx, item))

    # ── 小桶批量查询 ──

    def _run_mini_bucket_queries(
        self,
        mini_buckets: list,
        chain: list,
        primary_site: str,
        ctx: dict,
        skip_overflow: bool = False,
    ) -> list:
        """错峰执行小桶查询，冷却/配额感知，返回溢出条目列表。"""
        adapter_map = self._core.adapter_map
        rotator = self._core.rotator
        quota = self._core.quota

        overflow_items: list = []
        for mb_idx, (assigned_site, mini) in enumerate(mini_buckets):
            if mb_idx > 0:
                time.sleep(self._MINI_BUCKET_STAGGER)  # 小桶间错峰，防惊群效应

            # 冷却检测：分配站点冷却中时尝试回退，无回退则整桶溢出
            if rotator and rotator.get_cooldown_remaining(assigned_site) > 0:
                fallback_site = None
                for s in chain:
                    if s != assigned_site and (not rotator or rotator.get_cooldown_remaining(s) <= 0):
                        fallback_site = s
                        break
                if fallback_site:
                    logger.info(
                        "[MINI_BUCKET] mb=%d 站点=%s 冷却→%s",
                        mb_idx,
                        assigned_site,
                        fallback_site,
                    )
                    assigned_site = fallback_site
                else:
                    logger.warning(
                        "[MINI_BUCKET] mb=%d 站点=%s 无回退 溢出=%d",
                        mb_idx,
                        assigned_site,
                        len(mini),
                    )
                    # ✅ #46 P1: 冷却溢出计数器
                    m = ctx.get("metrics")
                    if m:
                        m.increment("overflow", count=len(mini))
                    overflow_items.extend(mini)
                    continue

            if quota and quota.get_search_remaining(assigned_site) < len(mini):
                logger.warning(
                    "[MINI_BUCKET] mb=%d 站点=%s 配额不足<%d 溢出=%d",
                    mb_idx,
                    assigned_site,
                    len(mini),
                    len(mini),
                )
                # ✅ #46 P1: 溢出计数器
                m = ctx.get("metrics")
                if m:
                    m.increment("overflow", count=len(mini))
                overflow_items.extend(mini)
                continue

            logger.info(
                "[MINI_BUCKET] mb=%d/%d 站点=%s 条目=%d",
                mb_idx + 1,
                len(mini_buckets),
                assigned_site,
                len(mini),
            )

            adapter = adapter_map.get(assigned_site)
            if not adapter:
                overflow_items.extend(mini)
                continue

            for idx, item in mini:
                self._process_single_query(
                    idx,
                    item,
                    assigned_site,
                    adapter,
                    ctx,
                    primary_site,
                    overflow_items,
                    skip_overflow,
                )

        return overflow_items
