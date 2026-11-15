"""P3-16 语义修复回归：LO 哨兵、单站重试一次、空链原因区分。"""

from __future__ import annotations

import threading
from types import SimpleNamespace

from pilotstd.core.status import Status
from pilotstd.query.engine import _mini_bucket as mini_mod
from pilotstd.query.engine import _overflow as overflow_mod
from pilotstd.query.engine._mini_bucket import MiniBucketHandler
from pilotstd.query.engine._overflow import OverflowHandler
from pilotstd.query.models import QueryResult


class _Metrics:
    def __init__(self):
        self.counts: dict[str, int] = {}

    def increment(self, key, count=1):
        self.counts[key] = self.counts.get(key, 0) + count


class _Core:
    def __init__(self, adapters: dict):
        self.adapter_map = adapters
        self.rotator = None
        self.cache = None
        self.recorded: list = []

    def record(self, site, n):
        self.recorded.append((site, n))


def _not_found() -> QueryResult:
    return QueryResult(standard_number="X 1-2020", error_message="未找到匹配结果", source_site="s1")


def _exact(site: str = "s1") -> QueryResult:
    r = QueryResult(standard_number="GB/T 1-2020", standard_name="标题", source_site=site)
    r.match_status = "exact"
    return r


class _Adapter:
    def __init__(self, results: list):
        self._results = list(results)
        self.calls = 0

    def query_with_strategy(self, *args):
        self.calls += 1
        return self._results.pop(0)


class _Routing:
    def __init__(self, chain):
        self._chain = chain

    def _build_chain_for_item(self, item, preferred_site=None):
        return list(self._chain)

    def _bucket_key(self, code, preferred_site=None):
        return self._chain[0] if self._chain else "other"


def _ctx(overflow_items, metrics):
    return {
        "results": {},
        "item_chains": {},
        "overflow_events": [],
        "metrics": metrics,
        "result_callback": None,
        "_record_usage": lambda s: None,
        "_record_match": lambda s, st: None,
        "_prog_lock": threading.Lock(),
        "_prog_ok": [0],
        "bump": lambda: None,
        "overflow_items": overflow_items,
    }


def test_not_found_sentinel_is_ng_not_lo(caplog, monkeypatch):
    # v2 配额扣减需要真实 routing service；单测里替换成永远可消费
    monkeypatch.setattr(mini_mod, "get_routing_service", lambda: SimpleNamespace(consume_quota=lambda s: True))
    adapter = _Adapter([_not_found()])
    handler = MiniBucketHandler(_Core({"s1": adapter}), _Routing(["s1"]), None)
    overflow: list = []
    metrics = _Metrics()
    ctx = _ctx(overflow, metrics)

    handler._process_single_query(0, ("GB/T", 1, 2020, "标题", None), "s1", adapter, ctx, "s1", overflow)

    assert 0 not in ctx["results"]
    assert ctx["item_chains"][0] == ["s1"]
    assert overflow == [(0, ("GB/T", 1, 2020, "标题", None))]
    assert "chain_exhausted" not in metrics.counts
    assert metrics.counts.get("no_result") == 1
    assert "[LO]" not in caplog.text


def test_mismatch_low_score_still_counts_as_lo(caplog, monkeypatch):
    monkeypatch.setattr(mini_mod, "get_routing_service", lambda: SimpleNamespace(consume_quota=lambda s: True))
    r = QueryResult(standard_number="GB/T 1-2019", standard_name="旧版", source_site="s1")
    r.match_status = "older"  # 50 分 -> LO 回池
    adapter = _Adapter([r])
    handler = MiniBucketHandler(_Core({"s1": adapter}), _Routing(["s1"]), None)
    overflow: list = []
    ctx = _ctx(overflow, _Metrics())

    handler._process_single_query(0, ("GB/T", 1, 2020, "标题", None), "s1", adapter, ctx, "s1", overflow)

    assert overflow == [(0, ("GB/T", 1, 2020, "标题", None))]


def test_single_site_chain_retries_once():
    # 主站此前已尝试过（tried=[s1]）→ 溢出循环跳过它；单站重试应补一次
    adapter = _Adapter([_exact("s1")])
    core = _Core({"s1": adapter})
    routing = _Routing(["s1"])
    handler = OverflowHandler(core, routing)
    state = {
        "results": {},
        "item_chains": {0: ["s1"]},
        "pending_reasons": [],
        "overflow_quota": {},
        "_try_overflow": lambda site: True,
        "metrics": _Metrics(),
        "bump": lambda: None,
        "_record_match": lambda s, st: None,
        "_prog_lock": threading.Lock(),
        "_prog_ok": [0],
    }

    handler._process_overflow_item(0, ("GB/T", 1, 2020, "标题", None), state, None, [0])

    assert state["results"][0].match_status == "exact"
    assert adapter.calls == 1
    assert state["_retried"] == {0}


def test_empty_chain_with_exhausted_quota_marks_quota_exhausted(monkeypatch):
    adapter = _Adapter([None])
    core = _Core({"s1": adapter})
    routing = _Routing([])
    handler = OverflowHandler(core, routing)

    fake_service = SimpleNamespace(quota=SimpleNamespace(all_exhausted=lambda: True))
    monkeypatch.setattr(overflow_mod, "get_routing_service", lambda: fake_service)
    metrics = _Metrics()
    state = {
        "results": {},
        "item_chains": {},
        "pending_reasons": [],
        "overflow_quota": {},
        "_try_overflow": lambda site: True,
        "metrics": metrics,
        "bump": lambda: None,
        "_record_match": lambda s, st: None,
        "_prog_lock": threading.Lock(),
        "_prog_ok": [0],
    }

    handler._process_overflow_item(0, ("GB/T", 1, 2020, "标题", None), state, None, [0])

    assert state["results"][0].match_status == "quota_exhausted"
    assert state["results"][0].status == Status.PENDING.value
    assert metrics.counts.get("quota_exhausted") == 1
    assert "chain_exhausted" not in metrics.counts
