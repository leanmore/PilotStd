# tests/query/engine/test_single_v2_route.py — U56 §7.2：v2 单条查询主链
"""覆盖 `pilotstd/query/engine/_single.py` 的 v2 路由主链（默认路径）。

2026-11-07 起 `is_v2_enabled()` 默认 True，日常单条查询走 `_query_one_v2`；
本文件锁定它的命中/配额/异常继续/决策记录/缓存跳过/preferred 绕过等 11 条契约。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pilotstd.query.engine import _single
from pilotstd.query.engine._single import SingleQueryHandler
from pilotstd.query.models import QueryResult
from pilotstd.query.routing.router_v2 import AllRoutesExhaustedException


@pytest.fixture(autouse=True)
def _stub_metrics(monkeypatch):
    """默认屏蔽指标/决策的副作用；需要断言的用例在用例内再覆盖。"""
    monkeypatch.setattr(_single, "build_decision", lambda *a: {})
    monkeypatch.setattr(_single, "record_decision", lambda d: None)
    monkeypatch.setattr(_single, "record_v2_skip", lambda *a: None)
    monkeypatch.setattr(_single, "record_v1_brief", lambda *a: None)


class _Adapter:
    """最小适配器替身：按 site_name 返回预设结果或抛异常。"""

    def __init__(self, site: str, result=None, exc: Exception | None = None) -> None:
        self.site_name = site
        self.site_label = site
        self._result = result
        self._exc = exc

    def query_with_strategy(self, *args, **kwargs):  # noqa: ANN002, ANN003
        if self._exc is not None:
            raise self._exc
        return self._result


class _Quota:
    def __init__(self, blocked: set[str] | None = None) -> None:
        self._blocked = blocked or set()

    def get_search_remaining(self, site: str) -> int:
        return 0 if site in self._blocked else 100


class _Cache:
    def __init__(self, hit=None) -> None:
        self._hit = hit
        self.puts: list = []

    def get(self, target, site):  # noqa: ANN001
        return self._hit

    def put(self, result) -> None:  # noqa: ANN001
        self.puts.append(result)


class _Core:
    def __init__(self, adapter_map=None, cache=None, use_cache: bool = False) -> None:
        self.adapters = list((adapter_map or {}).values())
        self.adapter_map = adapter_map or {}
        self.cache = cache if cache is not None else _Cache()
        self.use_cache = use_cache
        self.quota = _Quota()
        self.rotator = None
        self.metrics = None
        self.recorded: list[tuple[str, int]] = []

    def record(self, site: str, n: int) -> None:
        self.recorded.append((site, n))


class _Routing:
    def __init__(self, priority: list[str]) -> None:
        self._priority = priority

    def _get_priority(self, logical_code, preferred_site):  # noqa: ANN001
        return list(self._priority)


class _Service:
    """routing service 替身：链 + 配额 + 意图解析。"""

    def __init__(self, sites: list[str], quota_ok=None) -> None:
        self._sites = sites
        self._quota_ok = quota_ok or (lambda site: True)
        self.parser = SimpleNamespace(parse=lambda target: {"target": target})

    def get_route_chain(self, target):  # noqa: ANN001
        return SimpleNamespace(sites=list(self._sites))

    def consume_quota(self, site: str) -> bool:
        return bool(self._quota_ok(site))


def _found(name: str = "标准名", number: str = "GB/T 1-2020") -> QueryResult:
    return QueryResult(standard_number=number, standard_name=name, match_status="exact")


def _handler(core: _Core, priority: list[str] | None = None) -> SingleQueryHandler:
    return SingleQueryHandler(core, _Routing(priority or []))


def _v2_target() -> str:
    return "GB/T 1-2020"


# ── 1) 默认走 v2 ────────────────────────────────────────────────────────


def test_query_one_uses_v2_by_default(monkeypatch) -> None:
    """未设 ROUTING_ENGINE_VERSION 时，is_v2_enabled() 为 True 且走 _query_one_v2。"""
    monkeypatch.delenv("ROUTING_ENGINE_VERSION", raising=False)
    assert _single.is_v2_enabled() is True

    handler = _handler(_Core())
    sentinel = _found()
    called: list[tuple] = []
    monkeypatch.setattr(handler, "_query_one_v2", lambda *a: called.append(a) or sentinel)

    result = handler._query_one("GB/T", 1, 2020)
    assert result is sentinel
    assert len(called) == 1


# ── 2) 命中 ────────────────────────────────────────────────────────────


def test_query_one_v2_returns_first_site_hit(monkeypatch) -> None:
    """链 ["a","b"]、a 命中 → 返回结果、source_site 正确、record 记 1。"""
    core = _Core(adapter_map={"a": _Adapter("a", _found()), "b": _Adapter("b", _found())})
    handler = _handler(core)
    monkeypatch.setattr(_single, "get_routing_service", lambda: _Service(["a", "b"]))

    result = handler._query_one_v2(_v2_target(), "GB/T", 1, 2020, "", None, "")

    assert result.source_site == "a"
    assert core.recorded == [("a", 1)]


# ── 3) 配额耗尽跳过 ────────────────────────────────────────────────────


def test_query_one_v2_skips_site_when_quota_exhausted(monkeypatch) -> None:
    """consume_quota("a")=False → a 进 quota_skipped，继续 b。"""
    core = _Core(adapter_map={"a": _Adapter("a", _found()), "b": _Adapter("b", _found())})
    handler = _handler(core)
    svc = _Service(["a", "b"], quota_ok=lambda site: site != "a")
    monkeypatch.setattr(_single, "get_routing_service", lambda: svc)
    captured: dict = {}
    monkeypatch.setattr(_single, "build_decision", lambda *a: captured.setdefault("args", a))
    monkeypatch.setattr(_single, "record_decision", lambda d: None)

    result = handler._query_one_v2(_v2_target(), "GB/T", 1, 2020, "", None, "")

    assert result.source_site == "b"
    # build_decision(target, intent, chain_sites, tried, hit_site, hit_idx, quota_skipped, ms)
    assert captured["args"][6] == ["a"]


# ── 4) 异常继续 ────────────────────────────────────────────────────────


def test_query_one_v2_continues_after_adapter_exception(monkeypatch) -> None:
    """a 抛异常 → 记 warning 后继续，b 命中。"""
    core = _Core(
        adapter_map={
            "a": _Adapter("a", exc=RuntimeError("boom")),
            "b": _Adapter("b", _found()),
        }
    )
    handler = _handler(core)
    monkeypatch.setattr(_single, "get_routing_service", lambda: _Service(["a", "b"]))

    result = handler._query_one_v2(_v2_target(), "GB/T", 1, 2020, "", None, "")

    assert result.source_site == "b"
    assert core.recorded == [("b", 1)]


# ── 5) 补齐 standard_number ─────────────────────────────────────────────


def test_query_one_v2_fills_standard_number_when_missing(monkeypatch) -> None:
    """结果 standard_number="" → 填成 target。"""
    result = QueryResult(standard_number="", standard_name="标准名", match_status="exact")
    core = _Core(adapter_map={"a": _Adapter("a", result)})
    handler = _handler(core)
    monkeypatch.setattr(_single, "get_routing_service", lambda: _Service(["a"]))
    target = _v2_target()

    got = handler._query_one_v2(target, "GB/T", 1, 2020, "", None, "")

    assert got.standard_number == target


# ── 6) 全链失败 ────────────────────────────────────────────────────────


def test_query_one_v2_raises_all_routes_exhausted(monkeypatch) -> None:
    """全不命中 → AllRoutesExhaustedException，message 含 tried 链。"""
    core = _Core(
        adapter_map={
            "a": _Adapter("a", QueryResult(standard_number="x")),
            "b": _Adapter("b", QueryResult(standard_number="x")),
        }
    )
    handler = _handler(core)
    monkeypatch.setattr(_single, "get_routing_service", lambda: _Service(["a", "b"]))
    monkeypatch.setattr(_single, "record_decision", lambda d: None)
    monkeypatch.setattr(_single, "build_decision", lambda *a: {})

    with pytest.raises(AllRoutesExhaustedException) as exc:
        handler._query_one_v2(_v2_target(), "GB/T", 1, 2020, "", None, "")

    assert "a→b" in str(exc.value)


# ── 7) 失败也记录决策 ──────────────────────────────────────────────────


def test_query_one_v2_records_decision_on_exhaust(monkeypatch) -> None:
    """record_decision 收到 chain/tried/quota_skipped。"""
    core = _Core(adapter_map={"a": _Adapter("a", None)})
    handler = _handler(core)
    monkeypatch.setattr(_single, "get_routing_service", lambda: _Service(["a"]))
    captured: dict = {}
    monkeypatch.setattr(_single, "build_decision", lambda *a: captured.setdefault("args", a))
    monkeypatch.setattr(_single, "record_decision", lambda d: captured.setdefault("decision", d))

    with pytest.raises(AllRoutesExhaustedException):
        handler._query_one_v2(_v2_target(), "GB/T", 1, 2020, "", None, "")

    assert captured["args"][2] == ["a"]          # chain_sites
    assert captured["args"][3] == ["a"]          # tried
    assert captured["args"][4] is None           # hit_site
    assert "decision" in captured


# ── 8) 缓存命中记录 v2 skip ────────────────────────────────────────────


def test_query_one_cache_hit_records_v2_skip(monkeypatch) -> None:
    """缓存命中 → 不查适配器，record_v2_skip("cache_hit")。"""
    cached = _found()
    cached.source_site = "cache-site"
    core = _Core(adapter_map={"a": _Adapter("a", _found())}, cache=_Cache(hit=cached), use_cache=True)
    handler = _handler(core)
    skips: list[tuple] = []
    monkeypatch.setattr(_single, "record_v2_skip", lambda *a: skips.append(a))

    result = handler._query_one("GB/T", 1, 2020)

    assert result is cached
    assert skips and skips[0][1] == "cache_hit"


# ── 9) preferred_site 绕过 v2 ──────────────────────────────────────────


def test_query_one_preferred_site_bypasses_v2(monkeypatch) -> None:
    """指定站点 → 走 v1 链，并记录 record_v2_skip("preferred_site")。"""
    core = _Core(adapter_map={"a": _Adapter("a", _found())})
    handler = _handler(core, priority=["a"])
    skips: list[tuple] = []
    monkeypatch.setattr(_single, "record_v2_skip", lambda *a: skips.append(a))
    monkeypatch.setattr(_single, "record_v1_brief", lambda *a: None)
    monkeypatch.setattr(
        handler, "_query_one_v2", lambda *a: pytest.fail("preferred_site 不应走 v2")
    )

    result = handler._query_one("GB/T", 1, 2020, preferred_site="a")

    assert result.source_site == "a"
    assert any(item[1] == "preferred_site" for item in skips)


# ── 10) v1 配额耗尽友好错误 ────────────────────────────────────────────


def test_query_one_quota_exhausted_returns_friendly_error(monkeypatch) -> None:
    """v1 全配额 → “请明日再试”。"""
    monkeypatch.setenv("ROUTING_ENGINE_VERSION", "v1")
    core = _Core(adapter_map={"a": _Adapter("a", _found())})
    core.quota = _Quota(blocked={"a"})
    handler = _handler(core, priority=["a"])
    monkeypatch.setattr(_single, "record_v1_brief", lambda *a: None)

    result = handler._query_one("GB/T", 1, 2020)

    assert "请明日再试" in result.error_message


# ── 11) env=v1 时禁用 v2 ───────────────────────────────────────────────


def test_query_one_v2_disabled_when_env_v1(monkeypatch) -> None:
    """ROUTING_ENGINE_VERSION=v1 → 走 v1（不调用 v2）。"""
    monkeypatch.setenv("ROUTING_ENGINE_VERSION", "v1")
    core = _Core(adapter_map={"a": _Adapter("a", _found())})
    handler = _handler(core, priority=["a"])
    monkeypatch.setattr(_single, "record_v1_brief", lambda *a: None)
    monkeypatch.setattr(handler, "_query_one_v2", lambda *a: pytest.fail("v1 模式不应走 v2"))

    result = handler._query_one("GB/T", 1, 2020)

    assert result.source_site == "a"
