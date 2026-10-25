"""pick_best_result 行为契约（2026-10-25 从 6 个适配器抽取时锁定）。"""

from pilotstd.query.adapters.base import pick_best_result
from pilotstd.query.models import QueryResult


def _r(number: str, date: str = "") -> QueryResult:
    return QueryResult(standard_number=number, publish_date=date)


def test_empty_returns_none():
    assert pick_best_result([], "GB/T 19001-2016") is None


def test_exact_match_beats_newer_version():
    """精确命中优先：即使存在更晚发布的同号标准。"""
    exact = _r("GB/T 19001-2016", "2016-01-01")
    newer = _r("GB/T 19001-2020", "2020-01-01")
    assert pick_best_result([exact, newer], "GB/T 19001-2016") is exact


def test_no_exact_returns_latest_publish_date():
    older = _r("GB/T 19002-2010", "2010-01-01")
    newer = _r("GB/T 19002-2016", "2016-01-01")
    assert pick_best_result([older, newer], "GB/T 19001-2016") is newer


def test_missing_publish_date_treated_as_empty():
    """缺失日期按 "" 参与比较：任何真实日期都大于它，故有日期者胜出。"""
    no_date = _r("GB/T 19002-2010")
    dated = _r("GB/T 19003-2005", "2005-01-01")
    assert pick_best_result([no_date, dated], "GB/T 19001-2016") is dated


def test_tie_on_publish_date_returns_first_in_input_order():
    first = _r("GB/T 19002-2016", "2016-01-01")
    second = _r("GB/T 19003-2016", "2016-01-01")
    assert pick_best_result([first, second], "GB/T 19001-2016") is first


def test_multiple_exact_matches_returns_first_even_if_date_earlier():
    """多个精确命中时取迭代顺序第一个——证明走的是 for+return，不是先收集再取最晚。"""
    first_exact = _r("GB/T 19001-2016", "2016-01-01")
    second_exact = _r("GB/T 19001-2016", "2020-01-01")
    assert pick_best_result([first_exact, second_exact], "GB/T 19001-2016") is first_exact
