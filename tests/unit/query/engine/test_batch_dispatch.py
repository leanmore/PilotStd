"""BatchDispatcher Phase A 基线测试。"""

from __future__ import annotations

import threading
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


class TestSkippedIntegration:

    @pytest.mark.skip(reason="需要 ThreadPoolExecutor + 真实组件")
    def test_dispatch_queries(self):
        pass

    @pytest.mark.skip(reason="需要 mini_bucket 真实交互")
    def test_bucket_worker(self):
        pass

    @pytest.mark.skip(reason="_init_batch_state 创建 daemon 线程")
    def test_init_batch_state(self):
        pass

    @pytest.mark.skip(reason="依赖 _init_batch_state")
    def test_finalize_batch(self):
        pass
