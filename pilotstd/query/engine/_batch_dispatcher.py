# 模块：项目/查询/引擎/__分发器脚本
"""BatchDispatcher — 批量查询分发编排独立类（原 _BatchDispatchMixin 的 13 个方法）。

通过 _DispatchContext 注入 5 个组件 + 2 个配额常量，替代 MRO 隐式依赖。
多线程模型：ThreadPoolExecutor(max_workers=8) + daemon heartbeat(60s 轮询)。
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from pilotstd.core.config.paths import get_db_path
from pilotstd.core.db import Database

from ..models import QueryResult
from ..search_strategy import ADAPTER_TYPE_MAP
from ._constants import PROGRESS_TAG

if TYPE_CHECKING:
    from ._core_types import EngineCore
    from ._csres import CsresHandler
    from ._mini_bucket import MiniBucketHandler
    from ._report import ReportHandler
    from ._routing import RoutingHandler

logger = logging.getLogger(__name__)


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    import secrets

    return secrets.token_hex(4)


@dataclass(frozen=True)
class _DispatchContext:
    """BatchDispatcher 运行所需的不可变依赖上下文。"""

    core: "EngineCore"
    routing: "RoutingHandler"
    mini_bucket: "MiniBucketHandler"
    csres: "CsresHandler"
    report: "ReportHandler"
    ahbz_overflow_quota: int
    njbz_overflow_quota: int


class BatchDispatcher:
    """批量查询分发编排 — 组合注入到 BatchHandler。

    原 _BatchDispatchMixin 的 13 个方法全部迁入。
    """

    def __init__(self, ctx: _DispatchContext):
        self._ctx = ctx
        self._stop_event = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        BatchDispatcher._instance = self  # type: ignore[attr-defined]  # 供测试清理 fixture 访问

    # ── 心跳线程生命周期 ──

    def start_heartbeat(
        self,
        n: int,
        bucket_t0: float,
        prog_completed: list[int],
        prog_ok: list[int],
        prog_lock: threading.Lock,
    ) -> None:
        """启动进度心跳线程（幂等：已启动则跳过）。"""
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._stop_event.clear()

        def _progress_heartbeat() -> None:
            """每秒检查停止信号，每 60 秒输出一次批量查询进度心跳日志。"""
            tick = 0
            while not self._stop_event.wait(timeout=1.0):
                tick += 1
                if tick % 60 != 0:
                    continue
                with prog_lock:
                    c = prog_completed[0]
                    o = prog_ok[0]
                elapsed = time.time() - bucket_t0
                rate = c / max(elapsed, 0.001)
                eta = (n - c) / max(rate, 0.001) if rate > 0 else 0.0
                logger.info(
                    "%s 已完成=%d 总数=%d 成功=%d 速率=%.1f条/秒 预计剩余=%.0f秒",
                    PROGRESS_TAG, c, n, o, rate, eta,
                )

        self._heartbeat_thread = threading.Thread(target=_progress_heartbeat, daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self, timeout: float = 2.0) -> None:
        """停止心跳线程并等待退出。

        测试清理和桌面应用关闭时调用。线程安全，重复调用无副作用。
        """
        self._stop_event.set()
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=timeout)
        self._heartbeat_thread = None

    # ── 状态初始化 ──

    def _init_batch_state(
        self,
        n: int,
        progress_callback: Optional[Callable[[int], None]],
        metrics=None,
    ) -> dict:
        """初始化批量查询共享状态：计数器、进度心跳线程、结果容器。"""
        _bucket_t0 = time.time()
        results: Dict[int, QueryResult] = {}
        counter_lock = threading.Lock()
        counter = [0]

        _prog_completed = [0]
        _prog_ok = [0]
        _prog_lock = threading.Lock()
        _prog_stop = threading.Event()

        def bump() -> None:
            """原子递增进度计数器并回调，同时检查暂停事件。"""
            pause_event = self._ctx.core.pause_event
            if pause_event is not None:
                pause_event.wait()
            with counter_lock:
                counter[0] += 1
                if progress_callback:
                    progress_callback(counter[0])
            with _prog_lock:
                _prog_completed[0] += 1

        self.start_heartbeat(n, _bucket_t0, _prog_completed, _prog_ok, _prog_lock)

        return {
            "results": results,
            "bump": bump,
            "metrics": metrics,
            "_prog_completed": _prog_completed,
            "_prog_ok": _prog_ok,
            "_prog_lock": _prog_lock,
            "_prog_stop": _prog_stop,
            "_bucket_t0": _bucket_t0,
            "n": n,
        }

    # ── 分桶 ──

    def _bucket_items(
        self,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        preferred_site: str | None = None,
    ) -> Dict[str, List[Tuple[int, tuple[Any, ...]]]]:
        """将已解析条目按站点分桶。"""
        buckets: Dict[str, List[Tuple[int, tuple[Any, ...]]]] = {}
        for i, item in enumerate(parsed_list):
            key = self._ctx.routing._bucket_key(item[0], preferred_site)
            buckets.setdefault(key, []).append((i, item))
        for key, items in buckets.items():
            logger.info("[BUCKET] %s 总数=%d", key, len(items))
        return buckets

    # ── 分发上下文 ──

    def _setup_dispatch_context(
        self,
        state: dict,
        result_callback: Optional[Callable[[int, QueryResult], None]],
        progress_callback: Optional[Callable[[int], None]],
    ) -> None:
        """设置分发上下文：溢出配额、跟踪变量、匹配评分记录器。"""
        # 锁保护的共享状态：溢出配额、站点使用、匹配评分
        overflow_lock = threading.Lock()
        overflow_quota = {
            "ahbz": [self._ctx.ahbz_overflow_quota],
            "njbz365": [self._ctx.njbz_overflow_quota],
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

        csres_results: Dict[int, QueryResult] = {}
        csres_failures = [0]
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

        state.update({
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
        })

    # ── 桶工作线程 ──

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
            mini_buckets = self._ctx.mini_bucket._build_mini_buckets(bucket_items, chain, None)
            logger.info("[MINI_BUCKET] 用户指定站点=%s 总数=%d", preferred_site, len(bucket_items))
            overflow_items = self._ctx.mini_bucket._run_mini_bucket_queries(
                mini_buckets, chain, primary_site, state, skip_overflow=True
            )
            done = len(bucket_items) - len(overflow_items)
            return (overflow_items, time.time() - _ts, done)

        chain = self._ctx.routing._get_priority(
            bucket_items[0][1][0] if bucket_items else "", preferred_site
        )
        if primary_site in chain:
            chain = chain[chain.index(primary_site):]
        if not chain:
            chain = [primary_site]

        code = bucket_items[0][1][0]
        from ...core.std_utils import classify_std_code

        std_type = classify_std_code(code)
        type_route = ADAPTER_TYPE_MAP.get(std_type, {})
        weights = type_route.get("weights")

        mini_buckets = self._ctx.mini_bucket._build_mini_buckets(bucket_items, chain, weights)
        logger.info(
            "[MINI_BUCKET] %s 总数=%d 小桶=%d 链=%s 权重=%s",
            primary_site, len(bucket_items), len(mini_buckets),
            "→".join(chain), weights,
        )
        overflow_items = self._ctx.mini_bucket._run_mini_bucket_queries(
            mini_buckets, chain, primary_site, state
        )
        done = len(bucket_items) - len(overflow_items)
        return (overflow_items, time.time() - _ts, done)

    # ── 调度编排 ──

    def _dispatch_queries(
        self,
        buckets: Dict[str, List[Tuple[int, tuple[Any, ...]]]],
        state: dict,
        preferred_site: str | None = None,
    ) -> None:
        """调度编排：并行提交桶工作线程 + csres 后台线程，收集桶结果。"""
        # 国标/行标分流：/_→国标池，→行业池
        csres_pool_gb: list = []
        csres_pool_industry: list = []
        all_overflow: list = []
        bucket_futures: Dict[Any, str] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for bucket_key, items in buckets.items():
                if not items:
                    continue
                future = executor.submit(
                    self._bucket_worker, items, bucket_key, state, preferred_site
                )
                bucket_futures[future] = bucket_key
                if bucket_key in ("ahbz", "std_gov"):
                    csres_pool_gb.extend(items)
                elif bucket_key in ("hbba",):
                    csres_pool_industry.extend(items)

            csres_future = executor.submit(
                self._ctx.csres._run_csres_worker,
                csres_pool_gb,
                csres_pool_industry,
                state["csres_results"],
                state["csres_failures"],
                state.get("metrics"),
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
                        m = state.get("metrics")
                        if m:
                            m.increment("bucket_crash")
                    except Exception:
                        # 已知可忽略：metrics 计数失败不影响主流程
                        pass

            try:
                csres_future.result(timeout=600)
            except Exception:
                # 批次3-C5：等待 csres 后台结果失败必须记录（结果可能未合并），禁止静默吞错
                logger.warning(
                    "csres 后台结果等待失败: trace_id=%s source_type=query_dispatcher target_chat_id=-",
                    _log_trace_id(),
                    exc_info=True,
                )

        state["all_overflow"] = all_overflow

    # ── 结果收集 ──

    def _collect_csres_results(self, state: dict) -> None:
        """结果收集：将 csres 后台查询结果合并到主结果集。"""
        for idx, result in state["csres_results"].items():
            if idx not in state["results"]:
                state["results"][idx] = result
                with state["_prog_lock"]:
                    state["_prog_ok"][0] += 1
                state["bump"]()

    @staticmethod
    def _persist_batch_state(state: dict, n: int, completed: int) -> None:
        """batch_state 持久化写入。"""
        metrics = state.get("metrics")
        batch_id = metrics.batch_id if metrics else f"batch-legacy-{int(time.time())}"
        try:
            db = Database(get_db_path())
            overflow_json = json.dumps(
                [(idx, list(item)) for idx, item in state.get("all_overflow", [])[:200]],
                ensure_ascii=False,
            )
            snapshot_json = json.dumps(
                metrics.take_adapter_snapshot(state.get("_rotator"))
                if metrics and state.get("_rotator") else {},
                ensure_ascii=False,
            )
            db.execute(
                """INSERT OR REPLACE INTO batch_state
                   (batch_id, status, total_items, completed_items, failed_items,
                    overflow_pool, adapter_quota_snapshot, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (batch_id, "completed", n, completed, n - completed, overflow_json, snapshot_json),
            )
            logger.info("batch_state 已持久化: %s (completed=%d/%d)", batch_id, completed, n)
        except Exception:
            logger.exception("batch_state 持久化失败（非阻断）")

    # ── 收尾 ──

    def _finalize_batch(
        self,
        state: dict,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        n: int,
        temp_cooldown_skips: int,
    ) -> List[QueryResult]:
        """收尾：停止心跳 → 输出批量摘要报告 → 组装结果 → 重置状态。"""
        # 先停止心跳线程，确保后续 cleanup 期间不会有后台线程访问状态
        self.stop_heartbeat()

        # 组装报告摘要并委托处理器输出
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
        self._ctx.report._report_batch_summary(report)

        with state["_prog_lock"]:
            c = state["_prog_completed"][0]
            o = state["_prog_ok"][0]
        elapsed = time.time() - state["_bucket_t0"]
        logger.info(
            "%s 已完成=%d 总数=%d 成功=%d 速率=%.1f条/秒 预计剩余=0秒(完成)",
            PROGRESS_TAG, c, n, o, c / max(elapsed, 0.001),
        )

        self._ctx.core.query_active = False
        self._ctx.core.overflow_item_count = 0
        self._ctx.core.csres_active = False

        self._persist_batch_state(state, n, c)

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
