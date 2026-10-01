"""BatchDispatcher Phase A 基线测试。"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.query.engine._batch_dispatcher import BatchDispatcher, _DispatchContext
from pilotstd.query.models import QueryResult


@pytest.fixture
def ctx():
    core = MagicMock()
    core.pause_event = threading.Event()
    core.query_active = False
    routing = MagicMock()
    routing._bucket_key.return_value = "std_gov"
    mini_bucket = MagicMock()
    csres = MagicMock()
    report = MagicMock()
    return _DispatchContext(
        core=core, routing=routing, mini_bucket=mini_bucket,
        csres=csres, report=report,
        ahbz_overflow_quota=170, njbz_overflow_quota=200,
    )


@pytest.fixture
def dispatcher(ctx):
    return BatchDispatcher(ctx)


class TestBucketItems:

    def test_buckets_by_routing_key(self, dispatcher):
        parsed = [("GB", 1, 2020, "", None, "")]
        buckets = dispatcher._bucket_items(parsed)
        assert "std_gov" in buckets

    def test_empty_list(self, dispatcher):
        assert dispatcher._bucket_items([]) == {}

    def test_multiple_buckets(self, dispatcher, ctx):
        ctx.routing._bucket_key.side_effect = lambda c, _p=None: "A" if c == "GB" else "B"
        parsed = [("GB", 1, 2020, "", None, ""), ("SH", 2, 2021, "", None, "")]
        buckets = dispatcher._bucket_items(parsed)
        assert len(buckets) == 2


class TestSetupDispatchContext:

    def test_keys_added(self, dispatcher):
        state = {}
        dispatcher._setup_dispatch_context(state, None, None)
        for k in ("overflow_quota", "csres_results", "match_scores"):
            assert k in state

    def test_try_overflow_consumes_quota(self, dispatcher):
        state = {}
        dispatcher._setup_dispatch_context(state, None, None)
        assert state["_try_overflow"]("ahbz") is True
        for _ in range(169):
            state["_try_overflow"]("ahbz")
        assert state["_try_overflow"]("ahbz") is False

    def test_unknown_site_unlimited(self, dispatcher):
        state = {}
        dispatcher._setup_dispatch_context(state, None, None)
        assert state["_try_overflow"]("unknown") is True

    def test_record_usage(self, dispatcher):
        state = {}
        dispatcher._setup_dispatch_context(state, None, None)
        state["_record_usage"]("std_gov")
        state["_record_usage"]("std_gov")
        assert state["site_usage"]["std_gov"] == 2

    def test_record_match(self, dispatcher):
        state = {}
        dispatcher._setup_dispatch_context(state, None, None)
        state["_record_match"]("std_gov", "exact")
        state["_record_match"]("std_gov", "exact")
        assert state["match_scores"]["std_gov"]["exact"] == 2


class TestCollectCsresResults:

    def test_merges_into_main(self, dispatcher):
        state = {
            "csres_results": {0: QueryResult(standard_number="GB 1-2020", standard_name="CSRES")},
            "results": {},
            "_prog_lock": threading.Lock(),
            "_prog_ok": [0],
            "bump": lambda: None,
        }
        dispatcher._collect_csres_results(state)
        assert state["results"][0].standard_name == "CSRES"

    def test_skips_existing(self, dispatcher):
        existing = QueryResult(standard_number="GB 2-2020", standard_name="Existing")
        state = {
            "csres_results": {0: QueryResult(standard_number="GB 1-2020", standard_name="CSRES")},
            "results": {0: existing},
            "_prog_lock": threading.Lock(),
            "_prog_ok": [0],
            "bump": lambda: None,
        }
        dispatcher._collect_csres_results(state)
        assert state["results"][0].standard_name == "Existing"


class TestPersistBatchState:

    def test_exception_swallowed(self):
        with patch("pilotstd.query.engine._batch_dispatcher.Database", side_effect=Exception("DB down")), \
             patch("pilotstd.query.engine._batch_dispatcher.get_db_path", return_value=":memory:"):
            BatchDispatcher._persist_batch_state({"all_overflow": [], "metrics": None}, n=5, completed=5)


class TestBatchDispatchIntegration:
    """原 4 处永久 skip（T-29／R13-1）的真实替代覆盖——用 mock 驱动真实编排逻辑，不起外部依赖。"""

    def test_init_batch_state(self, dispatcher, ctx):
        """_init_batch_state：状态容器 + 心跳线程生命周期 + bump 回调/计数器。"""
        ctx.core.pause_event.set()  # 未暂停（Event 置位＝可推进；未置位时 bump 会阻塞等待）
        seen: list[int] = []
        state = dispatcher._init_batch_state(3, seen.append)

        try:
            assert state["n"] == 3
            assert state["results"] == {}
            assert dispatcher._heartbeat_thread is not None
            assert dispatcher._heartbeat_thread.is_alive()
            state["bump"]()
            state["bump"]()
            assert seen == [1, 2]
            assert state["_prog_completed"][0] == 2
        finally:
            dispatcher.stop_heartbeat()

        assert dispatcher._heartbeat_thread is None

    def test_bucket_worker(self, dispatcher, ctx):
        """_bucket_worker：指定站点走单链（skip_overflow），默认走优先级链；返回 (溢出, 耗时, 完成数)。"""
        item = (0, ("GB", 1, 2020, "", None, ""))
        ctx.mini_bucket._build_mini_buckets.return_value = {}
        ctx.mini_bucket._run_mini_bucket_queries.return_value = [item]
        ctx.routing._get_priority.return_value = ["std_gov"]

        overflow, elapsed, done = dispatcher._bucket_worker([item], "std_gov", {}, preferred_site="std_gov")
        assert overflow == [item]
        assert done == 0 and elapsed >= 0.0
        assert ctx.mini_bucket._run_mini_bucket_queries.call_args.kwargs["skip_overflow"] is True

        ctx.mini_bucket._run_mini_bucket_queries.return_value = []
        overflow2, _, done2 = dispatcher._bucket_worker([item], "std_gov", {})
        assert overflow2 == [] and done2 == 1

    def test_dispatch_queries(self, dispatcher, ctx):
        """_dispatch_queries：桶任务与 csres 后台任务并行执行，溢出项汇总进 state。"""
        state: dict = {}
        dispatcher._setup_dispatch_context(state, None, None)
        state.update({"_bucket_t0": time.time(), "metrics": None})
        ctx.routing._get_priority.return_value = ["std_gov"]
        ctx.mini_bucket._build_mini_buckets.return_value = {}
        overflow_item = (7, ("GB", 7, 2020, "", None, ""))
        ctx.mini_bucket._run_mini_bucket_queries.return_value = [overflow_item]
        ctx.csres._run_csres_worker.return_value = None
        buckets = {"std_gov": [(0, ("GB", 1, 2020, "", None, ""))]}

        dispatcher._dispatch_queries(buckets, state)

        assert state["all_overflow"] == [overflow_item]
        assert "std_gov" in state["bucket_times"]
        ctx.csres._run_csres_worker.assert_called_once()

    def test_finalize_batch(self, dispatcher, ctx, monkeypatch):
        """_finalize_batch：结果组装（未完成项兜底 error_message）+ 报告委托 + 状态复位。"""
        monkeypatch.setattr(BatchDispatcher, "_persist_batch_state", staticmethod(lambda *a, **kw: None))
        state: dict = {}
        dispatcher._setup_dispatch_context(state, None, None)
        state.update(
            {
                "_bucket_t0": time.time(),
                "_prog_completed": [1],
                "_prog_ok": [1],
                "_prog_lock": threading.Lock(),
                "results": {0: QueryResult(standard_number="GB 1-2020", standard_name="甲")},
                "n": 2,
                "_rotator": None,
                "metrics": None,
            }
        )
        parsed = [("GB", 1, 2020, "", None, ""), ("GB", 2, 2020, "", None, "")]

        out = dispatcher._finalize_batch(state, parsed, n=2, temp_cooldown_skips=0)

        assert out[0].standard_name == "甲"
        assert out[1].error_message == "查询未完成"
        ctx.report._report_batch_summary.assert_called_once()
        assert ctx.core.query_active is False
        assert ctx.core.overflow_item_count == 0
