# 模块：pilotstd/query/engine/_report.py
"""批量查询统计报告处理器 — 替代原 ReportMixin。

组合模式重构：ReportMixin → ReportHandler，依赖通过 EngineCore 注入。
辅助函数保留为模块级，保持与原代码逻辑一致。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._core_types import EngineCore

logger = logging.getLogger(__name__)


# ===== 模块级辅助函数 =====

# ── 桶统计 ──


def _log_bucket_quota(bucket_times: dict, site_usage: dict, _bucket_t0: float) -> None:
    """输出桶统计和站点配额日志。"""
    for key in sorted(bucket_times.keys()):
        start_t, end_t, done, ov = bucket_times[key]
        logger.info(
            "[BUCKET] %s 总数=%d 完成=%d 溢出=%d 耗时=%.1f秒",
            key,
            done + ov,
            done,
            ov,
            end_t - _bucket_t0,
        )
    logger.info("[TIMELINE] 桶数=%d 并发耗时=%.1f秒", len(bucket_times), time.time() - _bucket_t0)
    for site in sorted(site_usage.keys()):
        logger.info("[QUOTA] 站点=%s 已用=%d", site, site_usage[site])


# ── 溢出统计 ──


def _log_overflow_stats(
    overflow_events: list,
    item_chains: dict,
    csres_results: dict,
    csres_failures: list,
    match_scores: dict,
) -> None:
    """输出溢出时序、链路径、csres状态、站点评分卡日志。"""
    _chain_counts: dict[str, int] = {}
    for _idx, _chain in item_chains.items():
        _key = "→".join(_chain) if _chain else "none"
        _chain_counts[_key] = _chain_counts.get(_key, 0) + 1
    logger.info("[OVERFLOW] 事件=%d 链=%d", len(overflow_events), len(_chain_counts))
    for _chain_key, _cnt in sorted(_chain_counts.items(), key=lambda x: -x[1])[:5]:
        logger.info("[OVERFLOW_CHAIN] 路径=%s 次数=%d", _chain_key, _cnt)
    logger.info("[CSRES] 已处理=%d 失败=%d", len(csres_results), csres_failures[0])
    for site in sorted(match_scores.keys()):
        score_dist = " ".join(f"{k}={v}" for k, v in sorted(match_scores[site].items()))
        logger.info("[SCORE] 站点=%s %s", site, score_dist)


# ── 条目详情 ──


def _log_item_details(item_chains: dict, pending_reasons: list) -> None:
    """输出条目链追踪和待确认归因日志。"""
    for idx in sorted(item_chains.keys())[:20]:
        logger.info("[CHAIN] #%d %s", idx, "→".join(item_chains[idx]))
    for idx, chain_str in pending_reasons[:10]:
        logger.info("[PENDING] #%d 链=%s", idx, chain_str)


# ── 漏斗汇总 ──


def _log_funnel(
    n: int,
    results: dict,
    all_overflow: list,
    pending_reasons: list,
    _bucket_t0: float,
) -> None:
    """输出漏斗汇总和时间线日志。"""
    pending_count = len(pending_reasons)
    logger.info(
        "[FUNNEL] 总数=%d 成功=%d 溢出=%d 待确认=%d",
        n,
        len(results) - pending_count,
        len(all_overflow),
        pending_count,
    )
    logger.info("[TIMELINE] 逐桶查询完成 总数=%d 耗时=%.1f秒", n, time.time() - _bucket_t0)
    logger.info(
        "[BASELINE] 总数=%d 成功=%d 溢出=%d 待确认=%d 耗时=%.1f秒",
        n,
        len(results) - pending_count,
        len(all_overflow),
        pending_count,
        time.time() - _bucket_t0,
    )


class ReportHandler:
    """批量查询统计报告处理器 — 替代原 ReportMixin。

    依赖通过 EngineCore 注入，提供批量查询摘要报告功能。
    """

    _AHBZ_OVERFLOW_QUOTA: int = 170  # ahbz 溢出配额
    _NJBZ_OVERFLOW_QUOTA: int = 200  # njbz365 溢出配额

    def __init__(self, core: "EngineCore") -> None:
        self._core = core

    def _log_quota_water(self, overflow_quota: dict, temp_cooldown_skips: int) -> None:
        """输出配额水位和用量日志。"""
        _ahbz_used = self._AHBZ_OVERFLOW_QUOTA - overflow_quota["ahbz"][0]
        _njbz_used = self._NJBZ_OVERFLOW_QUOTA - overflow_quota["njbz365"][0]
        logger.info(
            "[WATER] ahbz溢出剩余=%d njbz365剩余=%d",
            overflow_quota["ahbz"][0],
            overflow_quota["njbz365"][0],
        )
        logger.info(
            "[QUOTA] 用量: ahbz=%d/%d njbz365=%d/%d 冷却跳过=%d",
            _ahbz_used,
            self._AHBZ_OVERFLOW_QUOTA,
            _njbz_used,
            self._NJBZ_OVERFLOW_QUOTA,
            temp_cooldown_skips,
        )
        logger.info("[RECOVERY] 临时冷却跳过=%d", temp_cooldown_skips)

    def _log_cache_hit_rate(self, n: int, results: dict) -> None:
        """输出缓存命中率日志。"""
        if not self._core.use_cache:
            return
        cache = self._core.cache
        if cache is None:
            return

        cache_hit = 0
        for i in range(n):
            if i in results:
                r = results[i]
                cached = cache.get(
                    r.standard_number if r.standard_number else "",
                    getattr(r, "source_site", ""),
                )
                if cached is not None:
                    cache_hit += 1
        if n > 0:
            logger.info(
                "[CACHE] 命中=%d 未命中=%d 命中率=%.1f%%",
                cache_hit,
                n - cache_hit,
                cache_hit / n * 100,
            )

    def _report_batch_summary(self, report: dict) -> None:
        """输出桶统计、站点配额、评分卡、链追踪等汇总日志。"""
        bucket_times = report["bucket_times"]
        site_usage = report["site_usage"]
        item_chains = report["item_chains"]
        overflow_events = report["overflow_events"]
        csres_results = report["csres_results"]
        csres_failures = report["csres_failures"]
        match_scores = report["match_scores"]
        pending_reasons = report["pending_reasons"]
        overflow_quota = report["overflow_quota"]
        temp_cooldown_skips = report["temp_cooldown_skips"]
        _bucket_t0 = report["_bucket_t0"]
        n = report["n"]
        all_overflow = report["all_overflow"]
        results = report["results"]

        self._core.overflow_item_count = 0

        _log_bucket_quota(bucket_times, site_usage, _bucket_t0)
        _log_overflow_stats(
            overflow_events,
            item_chains,
            csres_results,
            csres_failures,
            match_scores,
        )
        _log_item_details(item_chains, pending_reasons)
        self._log_quota_water(overflow_quota, temp_cooldown_skips)
        self._log_cache_hit_rate(n, results)
        _log_funnel(n, results, all_overflow, pending_reasons, _bucket_t0)
