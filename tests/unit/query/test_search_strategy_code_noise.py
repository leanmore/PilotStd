"""代号噪音归一化回归（2026-10-24）：`API STD 610` 应与查询 `API 610` 判为 exact。"""

from pilotstd.query.search_strategy import match_result


def test_api_std_prefix_is_exact() -> None:
    """站点返回 `API STD 610-2004`，不应因代号多出 STD 而判 mismatch。"""
    matched, status = match_result(
        "API", 610, 2004, "Centrifugal Pumps for Petroleum", "API STD 610-2004"
    )
    assert matched is True
    assert status == "exact"


def test_plain_code_still_exact() -> None:
    """无噪音后缀的写法保持原行为。"""
    matched, status = match_result("API", 610, 2004, "Centrifugal Pumps", "API 610-2004")
    assert matched is True
    assert status == "exact"


def test_different_number_still_mismatch() -> None:
    """剥噪音不能顺带放宽顺序号——号不同仍判 mismatch。"""
    matched, status = match_result("API", 610, 2004, "Pumps", "API STD 609-2004")
    assert matched is False
    assert status == "mismatch"
