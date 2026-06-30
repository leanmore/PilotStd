# pilotstd/query/engine/_batch.py
# 查询引擎批量查询混入模块
"""批量查询入口 + 逐桶查询引擎（V2）。"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..models import QueryResult
from ..search_strategy import ADAPTER_TYPE_MAP, MATCH_SCORE
from ._constants import PROGRESS_TAG
from ._csres import CsresMixin
from ._mini_bucket import MiniBucketMixin
from ._report import ReportMixin

logger = logging.getLogger(__name__)


class BatchMixin(CsresMixin, MiniBucketMixin, ReportMixin):
    """批量查询混入类 — query_standards + query_batch_parsed。"""

    # ── 二次分桶参数 ──
    _MINI_BUCKET_SIZE = 50
    _MINI_BUCKET_STAGGER = 5
    _CSRES_LIMIT = 50
    _CSRES_CIRCUIT_BREAK = 5
    _AHBZ_OVERFLOW_QUOTA = 170
    _NJBZ_OVERFLOW_QUOTA = 200

    def query_standards(
        self,
        items: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        use_parallel: Optional[bool] = None,
        force_refresh: bool = False,
        preferred_site: str = "",
    ) -> List[QueryResult]:
        """统一查询入口：所有端（CLI/Web/WinUI）均通过此方法查询。

        Args:
            items: [(logical_code, number, year, std_name, part, num_prefix), ...]
            progress_callback: 进度回调（每完成一条调用一次）
            result_callback: 结果回调（每完成一条调用一次）
            use_parallel: 是否强制并行（None=自动判断：长度≤1串行，>1并行）
            force_refresh: 是否跳过缓存强制实时查询

        内部策略：
            - 串行路径：逐条执行 _query_one()
            - 并行路径：逐桶查询引擎（桶内串行+桶间并行+CSRES+溢出回收）
        """
        n = len(items)
        if n == 0:
            return []
        # 自动判断：长度≤1 串行，>1 并行；use_parallel 可强制切换
        if use_parallel is False or (use_parallel is None and n <= 1):
            results: list[QueryResult] = []
            for i, item in enumerate(items):
                r = self._query_one(
                    logical_code=item[0],
                    number=item[1],
                    year=item[2],
                    std_name=item[3] if len(item) > 3 else "",
                    part=item[4] if len(item) > 4 else None,
                    force_refresh=force_refresh,
                    num_prefix=item[5] if len(item) > 5 else "",
                )
                results.append(r)
                if result_callback:
                    result_callback(i, r)
                if progress_callback:
                    progress_callback(i + 1)
            return results
        # 并行路径：委托给逐桶查询引擎
        return self.query_batch_parsed(
            items,
            progress_callback=progress_callback,
            result_callback=result_callback,
            preferred_site=preferred_site,
        )

    def query_batch_parsed(
        self,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        preferred_site: str = "",
    ) -> List[QueryResult]:
        """[已废弃] 使用 query_standards(items, use_parallel=True) 替代。
        仅保留作为 query_standards 并行路径的内部实现。外部调用请走 query_standards()。
        迁移时间：2026-06-24，阶段二统一查询引擎。"""
        import time as _time

        self._query_active = True

        _bucket_t0 = _time.time()
        n = len(parsed_list)
        results: Dict[int, QueryResult] = {}
        counter_lock = threading.Lock()
        counter = [0]

        def bump() -> None:
            with counter_lock:
                counter[0] += 1
                if progress_callback:
                    progress_callback(counter[0])
            with _prog_lock:
                _prog_completed[0] += 1

        # ── 0. 进度心跳线程（每60秒输出一次，三端统一格式）──
        _prog_completed = [0]
        _prog_ok = [0]
        _prog_lock = threading.Lock()
        _prog_stop = threading.Event()

        def _progress_heartbeat() -> None:
            while not _prog_stop.wait(60.0):
                with _prog_lock:
                    c = _prog_completed[0]
                    o = _prog_ok[0]
                elapsed = _time.time() - _bucket_t0
                rate = c / max(elapsed, 0.001)
                eta = (n - c) / max(rate, 0.001) if rate > 0 else 0.0
                logger.info(
                    "%s 已完成=%d 总数=%d 成功=%d 速率=%.1f条/秒 预计剩余=%.0f秒",
                    PROGRESS_TAG,
                    c,
                    n,
                    o,
                    rate,
                    eta,
                )

        _prog_thread = threading.Thread(target=_progress_heartbeat, daemon=True)
        _prog_thread.start()

        # ── 1. 分组 ──
        buckets: Dict[str, List[Tuple[int, tuple[Any, ...]]]] = {}
        for i, item in enumerate(parsed_list):
            key = self._bucket_key(item[0])
            buckets.setdefault(key, []).append((i, item))

        for key, items in buckets.items():
            logger.info("[BUCKET] %s 总数=%d", key, len(items))

        # ── 2. 全局溢出配额锁 ──
        overflow_lock = threading.Lock()
        overflow_quota = {
            "ahbz": [self._AHBZ_OVERFLOW_QUOTA],
            "njbz365": [self._NJBZ_OVERFLOW_QUOTA],
        }

        def _try_overflow(site: str) -> bool:
            """尝试从溢出池扣减配额，成功返回 True。"""
            if site not in overflow_quota:
                return True
            with overflow_lock:
                if overflow_quota[site][0] > 0:
                    overflow_quota[site][0] -= 1
                    return True
            return False

        # ── 3. csres 独立线程 ──
        csres_results: Dict[int, QueryResult] = {}
        csres_failures = [0]

        # ── 4. 桶工作线程 ──
        bucket_times: Dict[str, tuple[float, float, int, int]] = {}
        site_usage: Dict[str, int] = {}
        usage_lock = threading.Lock()

        def _record_usage(site: str) -> None:
            with usage_lock:
                site_usage[site] = site_usage.get(site, 0) + 1

        overflow_events: list[tuple[float, str, str, int]] = []
        match_scores: Dict[str, Dict[str, int]] = {}
        item_chains: Dict[int, list[str]] = {}
        pending_reasons: list[tuple[int, str]] = []
        score_lock = threading.Lock()

        def _record_match(site: str, status: str) -> None:
            with score_lock:
                if site not in match_scores:
                    match_scores[site] = {}
                match_scores[site][status] = match_scores[site].get(status, 0) + 1

        bucket_ctx = {
            "results": results,
            "item_chains": item_chains,
            "overflow_events": overflow_events,
            "match_scores": match_scores,
            "pending_reasons": pending_reasons,
            "_prog_lock": _prog_lock,
            "_prog_ok": _prog_ok,
            "overflow_quota": overflow_quota,
            "_try_overflow": _try_overflow,
            "_record_usage": _record_usage,
            "_record_match": _record_match,
            "bump": bump,
            "result_callback": result_callback,
            "progress_callback": progress_callback,
        }

        def _bucket_worker(
            bucket_items: List[Tuple[int, Tuple[str, int, int, str, Optional[int], str]]],
            primary_site: str,
        ) -> tuple[List[Tuple[int, Tuple[str, int, int, str, Optional[int], str]]], float, int]:
            """二次分桶 → 委托 _run_bucket 执行查询。"""
            _ts = _time.time()
            chain = self._get_priority(bucket_items[0][1][0]) if bucket_items else []
            chain = [s for s in chain if s != "csres"]
            if primary_site in chain:
                chain = chain[chain.index(primary_site) :]
            if not chain:
                chain = [primary_site]
            code = bucket_items[0][1][0]
            from ...core.std_utils import classify_std_code

            std_type = classify_std_code(code)
            type_route = ADAPTER_TYPE_MAP.get(std_type, {})
            weights = type_route.get("weights")
            mini_buckets = self._build_mini_buckets(bucket_items, chain, weights)
            logger.info(
                "[MINI_BUCKET] %s 总数=%d 小桶=%d 链=%s 权重=%s",
                primary_site,
                len(bucket_items),
                len(mini_buckets),
                "→".join(chain),
                weights,
            )
            overflow_items = self._run_mini_bucket_queries(mini_buckets, chain, primary_site, _time, bucket_ctx)
            done = len(bucket_items) - len(overflow_items)
            return (overflow_items, _time.time() - _ts, done)

        # ── 5. 桶间并行执行 ──
        csres_pool_gb = []
        csres_pool_industry = []
        all_overflow = []
        bucket_futures = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for bucket_key, items in buckets.items():
                if not items:
                    continue
                future = executor.submit(_bucket_worker, items, bucket_key)
                bucket_futures[future] = bucket_key
                # 收集 csres 候选条目（ahbz=GB主力桶, hbba=行业桶）
                if bucket_key in ("ahbz", "std_gov"):
                    csres_pool_gb.extend(items)
                elif bucket_key in ("hbba",):
                    csres_pool_industry.extend(items)

            # csres 独立线程
            csres_future = executor.submit(
                self._run_csres_worker, csres_pool_gb, csres_pool_industry, csres_results, csres_failures
            )

            # 收集桶结果
            for future in concurrent.futures.as_completed(bucket_futures):
                try:
                    overflow, elapsed, done = future.result()
                    key = bucket_futures[future]
                    bucket_times[key] = (
                        _bucket_t0,
                        _bucket_t0 + elapsed,
                        done,
                        len(overflow),
                    )
                    all_overflow.extend(overflow)
                except Exception:
                    logger.exception("桶执行异常: %s", bucket_futures[future])

            # 等待 csres 完成
            try:
                csres_future.result(timeout=600)
            except Exception:
                pass

        self._overflow_item_count = len(all_overflow)

        # ── 6. 合并 csres 结果 ──
        for idx, result in csres_results.items():
            if idx not in results:
                results[idx] = result
                with _prog_lock:
                    _prog_ok[0] += 1
                bump()

        # ── 7. 临时桶：链迭代（微批 + 抖动防惊群）──
        temp_cooldown_skips = 0
        if all_overflow:
            # 按剩余站点数升序
            all_overflow.sort(key=lambda x: len(self._build_chain_for_item(x[1])))
            # 微批：每批 20 条，批次间 2-5s 随机抖动
            batch_size = 20
            for batch_start in range(0, len(all_overflow), batch_size):
                batch = all_overflow[batch_start : batch_start + batch_size]
                if batch_start > 0:
                    import random as _random

                    jitter = _random.uniform(2, 5)
                    _time.sleep(jitter)
                for idx, item in batch:
                    if idx in results:
                        continue
                    chain = self._build_chain_for_item(item)
                    # 主站点已查过，从二线开始
                    start = 1 if chain and chain[0] == self._bucket_key(item[0]) else 0
                    found = False
                    tried_chain = item_chains.get(idx, [])
                    for site in chain[start:]:
                        if site not in self._adapter_map:
                            continue
                        if self._rotator and self._rotator.get_cooldown_remaining(site) > 0:
                            temp_cooldown_skips += 1
                            ov_q = overflow_quota.get(site, [0])
                            logger.debug(
                                "[QUOTA] 站点=%s 操作=溢出不可用 原因=冷却中 剩余溢出配额=%d",
                                site,
                                ov_q[0] if ov_q else 0,
                            )
                            continue
                        adapter = self._adapter_map[site]
                        # 溢出配额控制：受限站点消耗配额，配额耗尽则跳过
                        if site in overflow_quota and not _try_overflow(site):
                            logger.debug(
                                "[QUOTA] 站点=%s 操作=溢出配额耗尽 剩余=%d",
                                site,
                                overflow_quota[site][0],
                            )
                            continue
                        try:
                            _t0 = _time.time()
                            result = adapter.query_with_strategy(  # type: ignore[assignment]
                                item[0], item[1], item[2], item[3], item[4]
                            )
                            _elapsed = round(_time.time() - _t0, 3)
                            if self._rotator:
                                self._rotator.record_query_result(
                                    site,
                                    result is not None and result.is_found(),
                                    _elapsed,
                                )
                        except Exception:
                            continue
                        if result:
                            result.source_site = site
                            self._record(site, 1)
                            _record_match(site, getattr(result, "match_status", "err"))
                            tried_chain.append(site)
                            item_chains[idx] = tried_chain
                            score = MATCH_SCORE.get(getattr(result, "match_status", ""), 0)
                            _td = f"{item[0]} {item[1]}-{item[2]}"
                            if score >= 100:
                                results[idx] = result
                                with _prog_lock:
                                    _prog_ok[0] += 1
                                logger.info(
                                    "查询 [%s] [OK]%s(%s)",
                                    _td,
                                    site,
                                    getattr(result, "match_status", ""),
                                )
                                if result_callback and result.is_found():
                                    result_callback(idx, result)
                                bump()
                                found = True
                                break
                            else:
                                logger.info(
                                    "查询 [%s] [LO]%s(%s=%d) 未达100分继续",
                                    _td,
                                    site,
                                    getattr(result, "match_status", ""),
                                    score,
                                )
                    # 链耗尽→待确认
                    if not found:
                        chain_str = "→".join(item_chains.get(idx, [])) or "none"
                        _td2 = f"{item[0]} {item[1]}-{item[2]}"
                        logger.info("查询 [%s] [NG] tried=%s", _td2, chain_str)
                        pending_reasons.append((idx, chain_str))
                        results[idx] = QueryResult(
                            standard_number=f"{item[0]} {item[1]}-{item[2]}",
                            standard_name=item[3],
                            status="待确认",
                            source_site="",
                            match_status="chain_exhausted",
                        )
                        bump()

        self._report_batch_summary(
            {
                "bucket_times": bucket_times,
                "site_usage": site_usage,
                "item_chains": item_chains,
                "overflow_events": overflow_events,
                "csres_results": csres_results,
                "csres_failures": csres_failures,
                "match_scores": match_scores,
                "pending_reasons": pending_reasons,
                "overflow_quota": overflow_quota,
                "temp_cooldown_skips": temp_cooldown_skips,
                "_bucket_t0": _bucket_t0,
                "n": n,
                "all_overflow": all_overflow,
                "_time": _time,
                "results": results,
            }
        )

        # ── 停止进度心跳 + 最终进度 ──
        _prog_stop.set()
        with _prog_lock:
            c = _prog_completed[0]
            o = _prog_ok[0]
        elapsed = _time.time() - _bucket_t0
        logger.info(
            "%s 已完成=%d 总数=%d 成功=%d 速率=%.1f条/秒 预计剩余=0秒(完成)",
            PROGRESS_TAG,
            c,
            n,
            o,
            c / max(elapsed, 0.001),
        )

        # ── 8. 按原始顺序组装 + 状态重置 ──
        self._query_active = False
        self._overflow_item_count = 0
        self._csres_active = False
        return [
            results.get(
                i,
                QueryResult(
                    standard_number=f"{parsed_list[i][0]} {parsed_list[i][1]}-{parsed_list[i][2]}",
                    error_message="查询未完成",
                    source_site="",
                ),
            )
            for i in range(n)
        ]
