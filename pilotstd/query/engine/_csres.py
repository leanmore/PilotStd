# 模块：项目/查询/引擎/_脚本
"""CSRES 后台查询处理器 — 独立线程查询，替代原 CsresMixin。

组合模式重构：CsresMixin → CsresHandler，依赖通过 EngineCore 注入。
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._core_types import EngineCore

logger = logging.getLogger(__name__)
# 后台查询处理器，独立线程执行适配器查询，替代原


class CsresHandler:
    """CSRES 后台查询处理器 — 独立线程执行 CSRES 适配器查询。

    替代原 CsresMixin，所有依赖通过 EngineCore 访问。
    """

    _CSRES_LIMIT = 50  # 每次后台查询最多处理 50 条
    _CSRES_CIRCUIT_BREAK = 5  # 连续失败 5 次触发熔断，不再查询后续条目

    def __init__(self, core: "EngineCore") -> None:
        self._core = core

    # ___池—计算/行业各取多少条（60%+行业40%）
    def _build_csres_pool(self, gb_items: list, industry_items: list) -> list:
        """计算 GB/行业各取多少条（GB 60% + 行业 40%）。"""
        gb_take = int(self._CSRES_LIMIT * 0.6)  # GB 类取 60%
        industry_take = self._CSRES_LIMIT - gb_take  # 行业类取剩余 40%
        return gb_items[:gb_take] + industry_items[:industry_take]

    def _rate_limit_sleep(self, _last_ts: float, _t0: float) -> float:
        """计算并执行限速休眠，返回新的时间戳。"""
        base_interval = 5.0  # CSRES 基础查询间隔（秒）
        jitter = random.uniform(0, 1.0)  # 随机抖动，防止固定节律被识别
        query_elapsed = time.time() - _t0
        sleep_time = max(0, base_interval + jitter - query_elapsed)
        time.sleep(sleep_time)
        now = time.time()
        self._core.csres_processed += 1
        logger.info(
            "[CSRES_INTERVAL] 实际=%.1f秒 目标=%.1f秒 查询=%.1f秒 休眠=%.1f秒",
            now - _last_ts,
            base_interval + jitter,
            query_elapsed,
            sleep_time,
        )
        return now

    # ___工作者—后台查询线程：从/行业桶各取配额条目并发查询
    def _run_csres_worker(
        self,
        gb_items: list,
        industry_items: list,
        csres_results: dict,
        csres_failures: list,
        metrics=None,  # ✅ #46 P1: QueryMetrics 实例
    ) -> None:
        """CSRES 后台查询线程：从 GB/行业桶各取配额条目并发查询。

        原地修改 csres_results 和 csres_failures。
        """
        adapter = self._core.adapter_map.get("csres")
        if not adapter:
            return

        pool = self._build_csres_pool(gb_items, industry_items)
        self._core.csres_active = True
        self._core.csres_processed = 0
        self._core.csres_total = len(pool)

        _last_ts = time.time()
        for idx, item in pool:
            if csres_failures[0] >= self._CSRES_CIRCUIT_BREAK:
                # ✅#461:熔断计数器（含剩余丢弃条目数）
                items_processed = len(csres_results)
                items_dropped = len(pool) - items_processed
                if metrics:
                    metrics.increment("csres_meltdown", count=max(1, items_dropped))
                logger.warning(
                    "[CSRES_MELTDOWN] 连续失败=%d/%d 已处理=%d 丢弃=%d",
                    csres_failures[0],
                    self._CSRES_CIRCUIT_BREAK,
                    items_processed,
                    items_dropped,
                )
                break

            _t0 = time.time()
            try:
                result = adapter.query_with_strategy(item[0], item[1], item[2], num_prefix=item[3], part=item[4])
                _elapsed = round(time.time() - _t0, 3)

                rotator = self._core.rotator
                if rotator:
                    rotator.record_query_result(
                        "csres",
                        result is not None and result.is_found(),
                        _elapsed,
                    )

                if result:
                    result.source_site = "csres"
                    csres_results[idx] = result
                    csres_failures[0] = 0
                    logger.info(
                        "[CSRES] idx=%d code=%s num=%s %d-%d 状态=找到 评分=100",
                        idx,
                        item[0],
                        item[0],
                        item[1],
                        item[2],
                    )
                else:
                    csres_failures[0] += 1
                    logger.info(
                        "[CSRES] idx=%d code=%s num=%s %d-%d 状态=未找到 失败=%d/%d",
                        idx,
                        item[0],
                        item[0],
                        item[1],
                        item[2],
                        csres_failures[0],
                        self._CSRES_CIRCUIT_BREAK,
                    )
            except Exception:
                csres_failures[0] += 1
                logger.info(
                    "[CSRES] idx=%d code=%s 状态=错误 失败=%d/%d",
                    idx,
                    item[0],
                    csres_failures[0],
                    self._CSRES_CIRCUIT_BREAK,
                )

            _last_ts = self._rate_limit_sleep(_last_ts, _t0)

        self._core.csres_active = False
