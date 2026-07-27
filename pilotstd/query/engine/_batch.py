# pilotstd/query/engine/_batch.py
"""批量查询编排器 — 6 阶段流水线入口。分发/分桶/收尾已提取至 _batch_dispatch.py。"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from ..models import QueryResult
from ._batch_dispatch import _BatchDispatchMixin

if TYPE_CHECKING:
    from ._core_types import EngineCore
    from ._csres import CsresHandler
    from ._mini_bucket import MiniBucketHandler
    from ._overflow import OverflowHandler
    from ._report import ReportHandler
    from ._routing import RoutingHandler
    from ._single import SingleQueryHandler

logger = logging.getLogger(__name__)


class BatchHandler(_BatchDispatchMixin):
    """批量查询编排器 — 执行 6 阶段逐桶查询流水线。

    分发编排由 _BatchDispatchMixin 提供；本类负责入口调度和6阶段流水线编排。
    """

    _AHBZ_OVERFLOW_QUOTA = 170
    _NJBZ_OVERFLOW_QUOTA = 200

    # ── 入口 ──

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

    def query_standards(
        self,
        items: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        use_parallel: Optional[bool] = None,
        force_refresh: bool = False,
        preferred_site: str | None = None,
    ) -> List[QueryResult]:
        """统一查询入口：所有端（CLI/Web/WinUI）均通过此方法查询。"""
        n = len(items)
        if n == 0:
            return []

        # 单条目或显式串行 → 逐条查询
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
            items, progress_callback=progress_callback, result_callback=result_callback, preferred_site=preferred_site
        )

    def query_batch_parsed(
        self,
        parsed_list: List[Tuple[str, int, int, str, Optional[int], str]],
        progress_callback: Optional[Callable[[int], None]] = None,
        result_callback: Optional[Callable[[int, QueryResult], None]] = None,
        preferred_site: str | None = None,
    ) -> List[QueryResult]:
        """批量查询主流程：初始化 → 分桶 → 分发 → 收集 → 收尾。"""
        self._core.query_active = True
        n = len(parsed_list)

        # ✅ #46 P1: 创建批次级 Metrics 实例
        from ._metrics import QueryMetrics

        metrics = QueryMetrics(batch_id=f"batch-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}")

        try:
            # 6阶段流水线
            state = self._init_batch_state(n, progress_callback, metrics)
            buckets = self._bucket_items(parsed_list, preferred_site)
            self._setup_dispatch_context(state, result_callback, progress_callback)
            self._dispatch_queries(buckets, state, preferred_site)
            self._collect_csres_results(state)

            temp_cooldown_skips = self._overflow._handle_overflow(state, result_callback, preferred_site)
            return self._finalize_batch(state, parsed_list, n, temp_cooldown_skips)
        finally:
            # ✅ 任务4：归入 validate_failed 计数器 + 持久化 metrics
            try:
                from pilotstd.scan.parser._result_builder import get_validate_fail_count

                fail_count = get_validate_fail_count()
                if fail_count > 0:
                    metrics.increment("validate_failed", count=fail_count)
            except Exception:
                logger.exception("validate_failed 归入失败（非阻断）")
            try:
                metrics.persist_to_db()
            except Exception:
                logger.exception("metrics 持久化失败（非阻断）")
