# pilotstd/query/engine/_mini_bucket.py
# 小桶构建 + 查询执行混入 — 从 _batch.py 提取

import logging
from typing import Any, List, cast

from ..search_strategy import MATCH_SCORE

logger = logging.getLogger(__name__)


class MiniBucketMixin:
    """小桶拆分与逐桶查询执行（混入 BatchMixin）。"""

    def _build_mini_buckets(self, bucket_items: list, chain: list, weights: Any) -> list[tuple[str, list]]:
        """按权重或轮询将桶内条目拆分为 50 条小桶。"""
        if weights and len(weights) == len(chain):
            weights = cast(List[int], weights)
            cooled_sites: set[str] = set()
            if self._rotator:
                for site in chain:
                    if self._rotator.get_cooldown_remaining(site) > 0:
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
                        "[MINI_BUCKET] 冷却站点=%s 重分配权重=%s", ",".join(sorted(cooled_sites)), active_weights
                    )
            total_w = sum(active_weights)
            mini_buckets: list[tuple[str, list]] = []
            start = 0
            for i, site in enumerate(chain):
                if site in cooled_sites:
                    continue
                if i == len(chain) - 1:
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

    def _run_mini_bucket_queries(
        self, mini_buckets: list, chain: list, primary_site: str, _time: Any, ctx: dict
    ) -> list:
        """错峰执行小桶查询，冷却/配额感知，返回溢出条目列表。"""
        overflow_items = []
        for mb_idx, (assigned_site, mini) in enumerate(mini_buckets):
            if mb_idx > 0:
                _time.sleep(self._MINI_BUCKET_STAGGER)
            if self._rotator and self._rotator.get_cooldown_remaining(assigned_site) > 0:
                fallback_site = None
                for s in chain:
                    if s != assigned_site and (not self._rotator or self._rotator.get_cooldown_remaining(s) <= 0):
                        fallback_site = s
                        break
                if fallback_site:
                    logger.info("[MINI_BUCKET] mb=%d 站点=%s 冷却→%s", mb_idx, assigned_site, fallback_site)
                    assigned_site = fallback_site
                else:
                    logger.warning("[MINI_BUCKET] mb=%d 站点=%s 无回退 溢出=%d", mb_idx, assigned_site, len(mini))
                    overflow_items.extend(mini)
                    continue
            if self._quota and self._quota.get_search_remaining(assigned_site) < len(mini):
                logger.warning(
                    "[MINI_BUCKET] mb=%d 站点=%s 配额不足<%d 溢出=%d", mb_idx, assigned_site, len(mini), len(mini)
                )
                overflow_items.extend(mini)
                continue
            logger.info(
                "[MINI_BUCKET] mb=%d/%d 站点=%s 条目=%d", mb_idx + 1, len(mini_buckets), assigned_site, len(mini)
            )
            adapter = self._adapter_map.get(assigned_site)
            if not adapter:
                overflow_items.extend(mini)
                continue
            for idx, item in mini:
                if self._rotator and self._rotator.get_cooldown_remaining(assigned_site) > 0:
                    overflow_items.append((idx, item))
                    continue
                try:
                    _t0 = _time.time()
                    result = adapter.query_with_strategy(item[0], item[1], item[2], item[3], item[4])
                    _elapsed = round(_time.time() - _t0, 3)
                    if self._rotator:
                        self._rotator.record_query_result(
                            assigned_site, result is not None and result.is_found(), _elapsed
                        )
                except Exception:
                    ctx["item_chains"].setdefault(idx, []).append(assigned_site)
                    logger.warning("查询 [%s %s-%s] 异常 @%s", item[0], item[1], item[2], assigned_site)
                    overflow_items.append((idx, item))
                    continue
                target_display = f"{item[0]} {item[1]}-{item[2]}"
                if result:
                    result.source_site = assigned_site
                    self._record(assigned_site, 1)
                    ctx["_record_usage"](assigned_site)
                    ctx["_record_match"](assigned_site, getattr(result, "match_status", "err"))
                    score = MATCH_SCORE.get(getattr(result, "match_status", ""), 0)
                    ctx["item_chains"].setdefault(idx, []).append(assigned_site)
                    if score >= 100:
                        ctx["results"][idx] = result
                        with ctx["_prog_lock"]:
                            ctx["_prog_ok"][0] += 1
                        logger.info(
                            "查询 [%s] [OK]%s(%s)", target_display, assigned_site, getattr(result, "match_status", "")
                        )
                        self._cache.put(result)
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
                        ctx["overflow_events"].append((_time.time(), primary_site, assigned_site, idx))
                        overflow_items.append((idx, item))
                else:
                    ctx["item_chains"].setdefault(idx, []).append(assigned_site)
                    chain_str = "→".join(ctx["item_chains"].get(idx, []))
                    logger.info("查询 [%s] [NG]%s tried=%s", target_display, assigned_site, chain_str)
                    overflow_items.append((idx, item))
        return overflow_items
