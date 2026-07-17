# pilotstd/query/engine/_batch.py
"""批量查询编排器 — 6 阶段流水线，替代原 BatchMixin。

组合模式重构：BatchMixin → BatchHandler，组合 CsresHandler、MiniBucketHandler、
OverflowHandler、ReportHandler。
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from ..models import QueryResult
from ..search_strategy import ADAPTER_TYPE_MAP
from ._constants import PROGRESS_TAG

if TYPE_CHECKING:
    from ._core_types import EngineCore
    from ._csres import CsresHandler
    from ._mini_bucket import MiniBucketHandler
    from ._overflow import OverflowHandler
    from ._report import ReportHandler
    from ._routing import RoutingHandler
    from ._single import SingleQueryHandler

# BatchHandler — 批量查询编排器，执行 6 阶段逐桶查询流水线，替代原 BatchMixin
# 6 阶段：解析→分组→分发→CSRES 后台→小桶查询→溢出回收
logger = logging.getLogger(__name__)
# BatchHandler — 批量查询编排器，执行 6 阶段逐桶查询流水线，替代原 BatchMixin


class BatchHandler:
    """批量查询编排器 — 执行 6 阶段逐桶查询流水线。

    替代原 BatchMixin，组合所有子 Handler，通过 EngineCore 访问共享状态。
    """

    _AHBZ_OVERFLOW_QUOTA = 170  # ahbz 溢出回收配额上限
    _NJBZ_OVERFLOW_QUOTA = 200  # njbz365 溢出回收配额上限

    def __init__(
        self,
        core: "EngineCore",
        routing: "RoutingHandler",
        single: "SingleQueryHandler",
        csres: "CsresHandler",
        mini_bucket: "MiniBucketHandler",
        overflow: "OverflowHandler",
        report: "ReportHandler",
    ) -> None:
        self._core = core
        self._routing = routing
        self._single = single
        self._csres = csres
        self._mini_bucket = mini_bucket
        self._overflow = overflow
        self._report = report

    # ── 统一入口 ──

    # query_standards — 统一查询入口：所有端（CLI/Web/WinUI）均通过此方法查询
    def query_standards(
        self,
        items: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        use_parallel: Optional[bool] = None,
        force_refresh: bool = False,
        preferred_site: str | None = None,
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

        if use_parallel is False or (use_parallel is None and n <= 1):
            results: list[QueryResult] = []
            pause_event = self._core.pause_event
            for i, item in enumerate(items):
                if pause_event is not None:
                    pause_event.wait()
                r = self._single._query_one(
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

        return self.query_batch_parsed(
            items,
            progress_callback=progress_callback,
            result_callback=result_callback,
            preferred_site=preferred_site,
        )

    # ── 批量查询内部实现 ──

    def _init_batch_state(
        self,
        n: int,
        progress_callback: Optional[Callable[[int], None]],
    ) -> dict:
        """初始化批量查询共享状态：计数器、进度心跳线程、结果容器。"""
        _bucket_t0 = time.time()
        results: Dict[int, QueryResult] = {}
        counter_lock = threading.Lock()
        counter = [0]  # 用单元素列表包装 int，供嵌套函数 bump() 修改（nonlocal 变通）

        _prog_completed = [0]  # 进度：已完成计数
        _prog_ok = [0]  # 进度：成功计数
        _prog_lock = threading.Lock()
        _prog_stop = threading.Event()

        def bump() -> None:
            """原子递增进度计数器并回调，同时检查暂停事件。"""
            pause_event = self._core.pause_event
            if pause_event is not None:
                pause_event.wait()
            with counter_lock:
                counter[0] += 1
                if progress_callback:
                    progress_callback(counter[0])
            with _prog_lock:
                _prog_completed[0] += 1

        def _progress_heartbeat() -> None:
            """每 60 秒输出一次批量查询进度心跳日志（速率 + ETA）。"""
            while not _prog_stop.wait(60.0):
                with _prog_lock:
                    c = _prog_completed[0]
                    o = _prog_ok[0]
                elapsed = time.time() - _bucket_t0
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

    # ── 分桶与分发 ──

    def _bucket_items(
        self,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        preferred_site: str | None = None,
    ) -> Dict[str, List[Tuple[int, tuple[Any, ...]]]]:
        """将已解析条目按站点分桶。"""
        buckets: Dict[str, List[Tuple[int, tuple[Any, ...]]]] = {}
        for i, item in enumerate(parsed_list):
            key = self._routing._bucket_key(item[0], preferred_site)
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
        """设置分发上下文：溢出配额、跟踪变量、匹配评分记录器。"""
        overflow_lock = threading.Lock()
        # 溢出配额用单元素列表包装，供嵌套函数 _try_overflow 修改
        overflow_quota = {
            "ahbz": [self._AHBZ_OVERFLOW_QUOTA],
            "njbz365": [self._NJBZ_OVERFLOW_QUOTA],
        }

        def _try_overflow(site: str) -> bool:
            """尝试消耗一个溢出配额，返回 True 表示有余量。"""
            if site not in overflow_quota:
                return True
            with overflow_lock:
                if overflow_quota[site][0] > 0:
                    overflow_quota[site][0] -= 1
                    return True
            return False

        csres_results: Dict[int, QueryResult] = {}  # CSRES 后台查询结果暂存
        csres_failures = [0]  # CSRES 连续失败计数器

        bucket_times: Dict[str, tuple[float, float, int, int]] = {}  # 桶耗时统计
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

    # ── 桶工作线程 + 调度编排 ──

    # _bucket_worker — 二次分桶后委托 _run_mini_bucket_queries 执行查询
    def _bucket_worker(
        self,
        bucket_items: List[Tuple[int, Tuple[str, int, int, str, Optional[int], str]]],
        primary_site: str,
        state: dict,
        preferred_site: str | None = None,
    ) -> tuple:
        """二次分桶 → 委托 _run_mini_bucket_queries 执行查询。"""
        _ts = time.time()

        if preferred_site:
            chain = [preferred_site]
            mini_buckets = self._mini_bucket._build_mini_buckets(bucket_items, chain, None)
            logger.info(
                "[MINI_BUCKET] 用户指定站点=%s 总数=%d",
                preferred_site,
                len(bucket_items),
            )
            overflow_items = self._mini_bucket._run_mini_bucket_queries(
                mini_buckets, chain, primary_site, state, skip_overflow=True
            )
            done = len(bucket_items) - len(overflow_items)
            return (overflow_items, time.time() - _ts, done)

        chain = self._routing._get_priority(bucket_items[0][1][0] if bucket_items else "", preferred_site)
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

        mini_buckets = self._mini_bucket._build_mini_buckets(bucket_items, chain, weights)
        logger.info(
            "[MINI_BUCKET] %s 总数=%d 小桶=%d 链=%s 权重=%s",
            primary_site,
            len(bucket_items),
            len(mini_buckets),
            "→".join(chain),
            weights,
        )
        overflow_items = self._mini_bucket._run_mini_bucket_queries(mini_buckets, chain, primary_site, state)
        done = len(bucket_items) - len(overflow_items)
        return (overflow_items, time.time() - _ts, done)

    # _dispatch_queries — 调度编排：并行提交桶工作线程 + csres 后台线程
    def _dispatch_queries(
        self,
        buckets: Dict[str, List[Tuple[int, tuple[Any, ...]]]],
        state: dict,
        preferred_site: str | None = None,
    ) -> None:
        """调度编排：并行提交桶工作线程 + csres 后台线程，收集桶结果。"""
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
                if bucket_key in ("ahbz", "std_gov"):
                    csres_pool_gb.extend(items)
                elif bucket_key in ("hbba",):
                    csres_pool_industry.extend(items)

            csres_future = executor.submit(
                self._csres._run_csres_worker,
                csres_pool_gb,
                csres_pool_industry,
                state["csres_results"],
                state["csres_failures"],
            )

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

            try:
                csres_future.result(timeout=600)
            except Exception:
                pass

        state["all_overflow"] = all_overflow

    # ── 结果收集与收尾 ──

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
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        n: int,
        temp_cooldown_skips: int,
    ) -> List[QueryResult]:
        """收尾：输出批量摘要报告 → 停止心跳 → 组装结果 → 重置状态。"""
        report = {
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
            "results": state["results"],
        }
        self._report._report_batch_summary(report)

        state["_prog_stop"].set()
        with state["_prog_lock"]:
            c = state["_prog_completed"][0]
            o = state["_prog_ok"][0]
        elapsed = time.time() - state["_bucket_t0"]
        logger.info(
            "%s 已完成=%d 总数=%d 成功=%d 速率=%.1f条/秒 预计剩余=0秒(完成)",
            PROGRESS_TAG,
            c,
            n,
            o,
            c / max(elapsed, 0.001),
        )

        self._core.query_active = False
        self._core.overflow_item_count = 0
        self._core.csres_active = False
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

    # query_batch_parsed — [已废弃] 使用 query_standards(items, use_parallel=True) 替代
    def query_batch_parsed(
        self,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        preferred_site: str | None = None,
    ) -> List[QueryResult]:
        """[已废弃] 使用 query_standards(items, use_parallel=True) 替代。"""
        self._core.query_active = True
        n = len(parsed_list)

        state = self._init_batch_state(n, progress_callback)

        buckets = self._bucket_items(parsed_list, preferred_site)
        self._setup_dispatch_context(state, result_callback, progress_callback)

        self._dispatch_queries(buckets, state, preferred_site)

        self._collect_csres_results(state)

        temp_cooldown_skips = self._overflow._handle_overflow(state, result_callback, preferred_site)

        return self._finalize_batch(state, parsed_list, n, temp_cooldown_skips)
