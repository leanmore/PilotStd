# pilotstd/query/engine/_batch.py
# 查询引擎批量查询混入模块
"""批量查询入口 + 逐桶查询引擎（V2）。"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..models import QueryResult
from ..search_strategy import ADAPTER_TYPE_MAP
from ._constants import PROGRESS_TAG
from ._csres import CsresMixin
from ._mini_bucket import MiniBucketMixin
from ._overflow import OverflowHandler
from ._report import ReportMixin

logger = logging.getLogger(__name__)


class BatchMixin(CsresMixin, MiniBucketMixin, OverflowHandler, ReportMixin):
    """批量查询混入类 — query_standards + query_batch_parsed。"""

    _pause_event: Any
    _query_active: Any
    _overflow_item_count: Any
    _csres_active: Any
    _query_one: Any  # 由 SingleMixin 实现
    _get_priority: Any  # 由 RoutingMixin 实现

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
                # 暂停检查：若 _pause_event 被 clear()，在此阻塞直到 resume 调用 set()
                if self._pause_event is not None:
                    self._pause_event.wait()
                r = self._query_one(
                    logical_code=item[0],
                    number=item[1],
                    year=item[2],
                    std_name=item[3] if len(item) > 3 else "",
                    part=item[4] if len(item) > 4 else None,
                    force_refresh=force_refresh,
                    num_prefix=item[5] if len(item) > 5 else "",
                    preferred_site=preferred_site,
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

    # ── 批量查询子方法（query_batch_parsed 拆分）──

    def _init_batch_state(
        self,
        n: int,
        _time: Any,
        _bucket_t0: float,
        progress_callback: Optional[Callable[[int], None]],
    ) -> dict:
        """初始化批量查询共享状态：计数器、进度心跳线程、结果容器。
        返回 state dict 供后续子方法读写。
        """
        results: Dict[int, QueryResult] = {}
        counter_lock = threading.Lock()
        counter = [0]

        # 进度心跳变量（bump 闭包捕获，提前定义）
        _prog_completed = [0]
        _prog_ok = [0]
        _prog_lock = threading.Lock()
        _prog_stop = threading.Event()

        def bump() -> None:
            # 暂停检查：若 _pause_event 被 clear()，阻塞直到 resume 调用 set()
            if self._pause_event is not None:
                self._pause_event.wait()
            with counter_lock:
                counter[0] += 1
                if progress_callback:
                    progress_callback(counter[0])
            with _prog_lock:
                _prog_completed[0] += 1

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

        return {
            "results": results,
            "bump": bump,
            "_prog_completed": _prog_completed,
            "_prog_ok": _prog_ok,
            "_prog_lock": _prog_lock,
            "_prog_stop": _prog_stop,
            "_prog_thread": _prog_thread,
            "_bucket_t0": _bucket_t0,
            "n": n,
        }

    def _bucket_items(
        self,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        preferred_site: str = "",
    ) -> Dict[str, List[Tuple[int, tuple[Any, ...]]]]:
        """将已解析条目按站点分桶。"""
        buckets: Dict[str, List[Tuple[int, tuple[Any, ...]]]] = {}
        for i, item in enumerate(parsed_list):
            key = self._bucket_key(item[0], preferred_site)
            buckets.setdefault(key, []).append((i, item))
        for key, items in buckets.items():
            logger.info("[BUCKET] %s 总数=%d", key, len(items))
        return buckets

    def _setup_dispatch_context(
        self,
        state: dict,
        result_callback: Optional[Callable[[int, QueryResult], None]],
        progress_callback: Optional[Callable[[int], None]],
    ) -> None:
        """设置分发上下文：溢出配额、跟踪变量、匹配评分记录器。
        原地修改 state dict，添加 dispatch 阶段需要的所有键。
        """
        # 全局溢出配额锁
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

        # csres 独立线程结果容器
        csres_results: Dict[int, QueryResult] = {}
        csres_failures = [0]

        # 桶工作跟踪变量
        bucket_times: Dict[str, tuple[float, float, int, int]] = {}
        site_usage: Dict[str, int] = {}
        usage_lock = threading.Lock()

        def _record_usage(site: str) -> None:
            with usage_lock:
                site_usage[site] = site_usage.get(site, 0) + 1

        # 匹配评分与链追踪
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

        state.update(
            {
                "overflow_quota": overflow_quota,
                "_try_overflow": _try_overflow,
                "csres_results": csres_results,
                "csres_failures": csres_failures,
                "bucket_times": bucket_times,
                "site_usage": site_usage,
                "_record_usage": _record_usage,
                "overflow_events": overflow_events,
                "match_scores": match_scores,
                "item_chains": item_chains,
                "pending_reasons": pending_reasons,
                "_record_match": _record_match,
                "result_callback": result_callback,
                "all_overflow": [],
            }
        )

    def _bucket_worker(
        self,
        bucket_items: List[Tuple[int, Tuple[str, int, int, str, Optional[int], str]]],
        primary_site: str,
        state: dict,
        preferred_site: str = "",
    ) -> tuple:
        """二次分桶 → 委托 _run_mini_bucket_queries 执行查询。
        返回 (溢出条目列表, 耗时, 已完成数)。
        """
        import time as _time2

        _ts = _time2.time()
        chain = self._get_priority(bucket_items[0][1][0] if bucket_items else "", preferred_site)
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
        overflow_items = self._run_mini_bucket_queries(mini_buckets, chain, primary_site, _time2, state)
        done = len(bucket_items) - len(overflow_items)
        return (overflow_items, _time2.time() - _ts, done)

    def _dispatch_queries(
        self,
        buckets: Dict[str, List[Tuple[int, tuple[Any, ...]]]],
        state: dict,
        preferred_site: str = "",
    ) -> None:
        """调度编排：并行提交桶工作线程 + csres 后台线程，收集桶结果。
        原地修改 state["all_overflow"]、state["bucket_times"] 等。
        """
        csres_pool_gb: list = []
        csres_pool_industry: list = []
        all_overflow: list = []
        bucket_futures: Dict[Any, str] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for bucket_key, items in buckets.items():
                if not items:
                    continue
                future = executor.submit(self._bucket_worker, items, bucket_key, state, preferred_site)
                bucket_futures[future] = bucket_key
                # 收集 csres 候选条目（ahbz=GB主力桶, hbba=行业桶）
                if bucket_key in ("ahbz", "std_gov"):
                    csres_pool_gb.extend(items)
                elif bucket_key in ("hbba",):
                    csres_pool_industry.extend(items)

            # csres 独立线程
            csres_future = executor.submit(
                self._run_csres_worker,
                csres_pool_gb,
                csres_pool_industry,
                state["csres_results"],
                state["csres_failures"],
            )

            # 收集桶结果
            for future in concurrent.futures.as_completed(bucket_futures):
                try:
                    overflow, elapsed, done = future.result()
                    key = bucket_futures[future]
                    state["bucket_times"][key] = (
                        state["_bucket_t0"],
                        state["_bucket_t0"] + elapsed,
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

        state["all_overflow"] = all_overflow

    def _collect_csres_results(self, state: dict) -> None:
        """结果收集：将 csres 后台查询结果合并到主结果集。"""
        for idx, result in state["csres_results"].items():
            if idx not in state["results"]:
                state["results"][idx] = result
                with state["_prog_lock"]:
                    state["_prog_ok"][0] += 1
                state["bump"]()

    def _finalize_batch(
        self,
        state: dict,
        _time: Any,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        n: int,
        temp_cooldown_skips: int,
    ) -> List[QueryResult]:
        """收尾：输出批量摘要报告 → 停止心跳 → 组装结果 → 重置状态。"""
        # 输出批量摘要报告
        self._report_batch_summary(
            {
                "bucket_times": state["bucket_times"],
                "site_usage": state["site_usage"],
                "item_chains": state["item_chains"],
                "overflow_events": state["overflow_events"],
                "csres_results": state["csres_results"],
                "csres_failures": state["csres_failures"],
                "match_scores": state["match_scores"],
                "pending_reasons": state["pending_reasons"],
                "overflow_quota": state["overflow_quota"],
                "temp_cooldown_skips": temp_cooldown_skips,
                "_bucket_t0": state["_bucket_t0"],
                "n": state["n"],
                "all_overflow": state["all_overflow"],
                "_time": _time,
                "results": state["results"],
            }
        )

        # 停止进度心跳 + 最终进度
        state["_prog_stop"].set()
        with state["_prog_lock"]:
            c = state["_prog_completed"][0]
            o = state["_prog_ok"][0]
        elapsed = _time.time() - state["_bucket_t0"]
        logger.info(
            "%s 已完成=%d 总数=%d 成功=%d 速率=%.1f条/秒 预计剩余=0秒(完成)",
            PROGRESS_TAG,
            c,
            n,
            o,
            c / max(elapsed, 0.001),
        )

        # 按原始顺序组装 + 状态重置
        self._query_active = False
        self._overflow_item_count = 0
        self._csres_active = False
        return [
            state["results"].get(
                i,
                QueryResult(
                    standard_number=f"{parsed_list[i][0]} {parsed_list[i][1]}-{parsed_list[i][2]}",
                    error_message="查询未完成",
                    source_site="",
                ),
            )
            for i in range(n)
        ]

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

        # 1) 初始化进度心跳 + 结果容器
        state = self._init_batch_state(n, _time, _bucket_t0, progress_callback)

        # 2) 分桶 + 设置分发上下文（溢出配额、跟踪变量）
        buckets = self._bucket_items(parsed_list, preferred_site)
        self._setup_dispatch_context(state, result_callback, progress_callback)

        # 3) 调度查询：桶并行 + csres 后台线程
        self._dispatch_queries(buckets, state, preferred_site)

        # 4) 合并 csres 结果
        self._collect_csres_results(state)

        # 5) 处理溢出：链迭代 + 冷却/配额恢复
        temp_cooldown_skips = self._handle_overflow(state, _time, result_callback)

        # 6) 报告 + 最终化 + 组装结果
        return self._finalize_batch(state, _time, parsed_list, n, temp_cooldown_skips)
