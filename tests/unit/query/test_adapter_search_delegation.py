"""6 个适配器 `_search` 与 pick_best_result 的等价性（2026-10-25）。

替换前：两者各自实现，测试证明结果一致；
替换后：`_search` 改为委托，同一测试继续通过 → 证明替换未改变行为。
注意：只覆盖委托层，`query_standards` 的网络/解析路径仍无测试（见技术债 A-12）。
"""

import pytest

from pilotstd.query.adapters.base import pick_best_result
from pilotstd.query.adapters.ccsn import CCSNAdapter
from pilotstd.query.adapters.jtst import JTSTAdapter
from pilotstd.query.adapters.mee import MEEAdapter
from pilotstd.query.adapters.nrsis import NRSISAdapter
from pilotstd.query.adapters.sppt import SPPTAdapter
from pilotstd.query.adapters.sppt_local import SPPTLocalAdapter
from pilotstd.query.models import QueryResult

ADAPTERS = [
    ("ccsn", CCSNAdapter),
    ("sppt", SPPTAdapter),
    ("sppt_local", SPPTLocalAdapter),
    ("jtst", JTSTAdapter),
    ("mee", MEEAdapter),
    ("nrsis", NRSISAdapter),
]


def _r(number: str, date: str = "") -> QueryResult:
    return QueryResult(standard_number=number, publish_date=date)


@pytest.mark.parametrize(("name", "adapter_cls"), ADAPTERS)
def test_search_result_equals_helper(name, adapter_cls):
    adapter = adapter_cls()
    exact = _r("GB/T 19001-2016", "2016-01-01")
    newer = _r("GB/T 19001-2020", "2020-01-01")
    candidates = [newer, exact]
    # 实例属性遮蔽方法：只验证 `_search` 的挑选逻辑，不触网
    adapter.query_standards = lambda _term: candidates  # type: ignore[method-assign]
    result = adapter._search("GB/T 19001-2016")
    assert result is exact
    assert result is pick_best_result(candidates, "GB/T 19001-2016")


@pytest.mark.parametrize(("name", "adapter_cls"), ADAPTERS)
def test_search_empty_returns_none(name, adapter_cls):
    adapter = adapter_cls()
    adapter.query_standards = lambda _term: []  # type: ignore[method-assign]
    assert adapter._search("GB/T 19001-2016") is None
