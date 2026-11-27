"""P0 聚合搜索单测：默认关闭 / 合并去重 / 置信度 / 超时隔离 / 异常隔离 / max_sites。"""

from __future__ import annotations

import time
from types import SimpleNamespace

from pilotstd.query.aggregation import (
    CONFIG_ENABLED,
    CONFIG_MAX_SITES,
    CONFIG_PER_SITE_TIMEOUT,
    CONFIG_TOTAL_BUDGET,
    AggregationService,
)
from pilotstd.query.models import QueryResult


class FakeConfig:
    """最小配置桩：`get(key, default)`。"""

    def __init__(self, **values: object) -> None:
        self._values = values

    def get(self, key: str, default: object = None) -> object:
        return self._values.get(key, default)


class FakeAdapter:
    """假适配器：返回预置结果，可注入延迟/异常，并记录调用次数。"""

    def __init__(self, site: str, rows: list[QueryResult], delay: float = 0.0, boom: bool = False) -> None:
        self._site = site
        self._rows = rows
        self._delay = delay
        self._boom = boom
        self.calls: list[str] = []

    @property
    def site_name(self) -> str:
        return self._site

    def _search_candidates(self, term: str) -> list[QueryResult]:
        self.calls.append(term)
        if self._delay:
            time.sleep(self._delay)
        if self._boom:
            raise RuntimeError("boom")
        return list(self._rows)


class FakeRouting:
    """假路由：返回固定站点顺序。"""

    def __init__(self, sites: list[str]) -> None:
        self._sites = sites

    def get_route_chain(self, query: str):  # noqa: ANN201
        return SimpleNamespace(sites=[SimpleNamespace(site_name=s) for s in self._sites])


def enabled_cfg(**over: object) -> FakeConfig:
    base: dict[str, object] = {
        CONFIG_ENABLED: True,
        CONFIG_PER_SITE_TIMEOUT: 2.0,
        CONFIG_TOTAL_BUDGET: 4.0,
        CONFIG_MAX_SITES: 6,
    }
    base.update(over)
    return FakeConfig(**base)


def row(number: str, name: str = "某标准", status: str = "现行") -> QueryResult:
    return QueryResult(standard_number=number, standard_name=name, status=status)


class TestDisabled:
    def test_disabled_by_default(self) -> None:
        adapter = FakeAdapter("site_a", [row("GB/T 1.1-2020")])
        service = AggregationService(adapters=[adapter], config=FakeConfig())
        result = service.search("GB/T 1.1-2020")
        assert result.enabled is False
        assert result.items == []
        assert adapter.calls == []


class TestMerge:
    def test_same_number_merged_with_sources_and_exact(self) -> None:
        a = FakeAdapter("std_gov", [row("GB/T 1.1-2020", "标准化工作导则", "现行")])
        b = FakeAdapter("csres", [row("GB/T 1.1-2020", "标准化工作导则", "现行")])
        service = AggregationService(adapters=[a, b], routing=FakeRouting(["std_gov", "csres"]), config=enabled_cfg())
        result = service.search("GB/T 1.1-2020")
        assert result.enabled is True
        assert len(result.items) == 1
        item = result.items[0]
        assert item.sources == ["std_gov", "csres"]
        assert item.confidence == "exact"
        assert item.status_key == "active"

    def test_keyword_query_keeps_distinct_numbers(self) -> None:
        a = FakeAdapter("std_gov", [row("GB/T 1.1-2020"), row("GB/T 1.2-2020")])
        service = AggregationService(adapters=[a], routing=FakeRouting(["std_gov"]), config=enabled_cfg())
        result = service.search("标准化 导则")
        assert {i.standard_number for i in result.items} == {"GB/T 1.1-2020", "GB/T 1.2-2020"}
        assert all(i.confidence == "keyword" for i in result.items)

    def test_exact_item_sorted_before_keyword(self) -> None:
        a = FakeAdapter("std_gov", [row("GB/T 2.1-2019"), row("GB/T 1.1-2020")])
        service = AggregationService(adapters=[a], routing=FakeRouting(["std_gov"]), config=enabled_cfg())
        result = service.search("GB/T 1.1-2020")
        assert [i.standard_number for i in result.items] == ["GB/T 1.1-2020", "GB/T 2.1-2019"]
        assert result.items[0].confidence == "exact"
        assert result.items[1].confidence == "keyword"


class TestIsolation:
    def test_slow_site_times_out_but_fast_site_returns(self) -> None:
        fast = FakeAdapter("fast", [row("GB/T 1.1-2020")])
        slow = FakeAdapter("slow", [row("GB/T 9.9-2020")], delay=0.6)
        cfg = enabled_cfg(**{CONFIG_PER_SITE_TIMEOUT: 0.1, CONFIG_TOTAL_BUDGET: 0.2})
        service = AggregationService(adapters=[fast, slow], routing=FakeRouting(["fast", "slow"]), config=cfg)
        result = service.search("GB/T 1.1-2020")
        by_site = {o.site: o for o in result.sites}
        assert by_site["fast"].ok is True
        assert by_site["slow"].ok is False and by_site["slow"].error == "timeout"
        assert [i.standard_number for i in result.items] == ["GB/T 1.1-2020"]

    def test_adapter_exception_isolated(self) -> None:
        bad = FakeAdapter("bad", [], boom=True)
        good = FakeAdapter("good", [row("DB50/T 950-2026")])
        service = AggregationService(adapters=[bad, good], routing=FakeRouting(["bad", "good"]), config=enabled_cfg())
        result = service.search("DB50/T 950-2026")
        by_site = {o.site: o for o in result.sites}
        assert by_site["bad"].ok is False and by_site["bad"].error == "RuntimeError"
        assert [i.standard_number for i in result.items] == ["DB50/T 950-2026"]


class TestLimits:
    def test_max_sites_caps_candidates(self) -> None:
        adapters = [FakeAdapter(f"s{i}", [row(f"GB/T {i}.1-2020")]) for i in range(5)]
        cfg = enabled_cfg(**{CONFIG_MAX_SITES: 2})
        service = AggregationService(
            adapters=adapters, routing=FakeRouting([f"s{i}" for i in range(5)]), config=cfg
        )
        service.search("GB/T 1.1-2020", max_sites=2)
        assert sum(len(a.calls) for a in adapters) == 2

    def test_missing_adapter_reported_not_fatal(self) -> None:
        good = FakeAdapter("good", [row("GB/T 1.1-2020")])
        service = AggregationService(adapters=[good], routing=FakeRouting(["good", "missing"]), config=enabled_cfg())
        result = service.search("GB/T 1.1-2020")
        by_site = {o.site: o for o in result.sites}
        assert by_site["missing"].ok is False and "unavailable" in by_site["missing"].error
        assert result.items

    def test_result_to_dict_is_jsonable(self) -> None:
        import json

        a = FakeAdapter("std_gov", [row("GB/T 1.1-2020")])
        service = AggregationService(adapters=[a], routing=FakeRouting(["std_gov"]), config=enabled_cfg())
        payload = service.search("GB/T 1.1-2020").to_dict()
        assert json.loads(json.dumps(payload))["items"][0]["standard_number"] == "GB/T 1.1-2020"
