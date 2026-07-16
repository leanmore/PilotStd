# tests/gui/test_e2e_query_summary.py
"""E2E 测试 — QuerySummaryHandler.build_buckets 核心路径。"""

from __future__ import annotations

import pytest

from pilotstd.models import ParsedStdInfo


def _make_parsed(
    logical_code: str = "GB/T",
    number: int = 1,
    year: int = 2020,
    std_name: str = "",
    found_name: str = "",
    next_action: str = "",
    stage_status: str = "",
    effect_status: str = "",
    is_adopted: bool = False,
) -> ParsedStdInfo:
    return ParsedStdInfo(
        raw_filename=f"{logical_code} {number}-{year}.pdf",
        logical_code=logical_code,
        number=number,
        year=year,
        std_name=std_name,
        found_name=found_name,
        next_action=next_action,
        stage_status=stage_status,
        effect_status=effect_status,
        is_adopted=is_adopted,
    )


@pytest.mark.e2e
def test_build_buckets_empty(window, qtbot):
    """build_buckets: 空 parsed_results 返回 7 个空桶。"""
    handler = window._core.query._summary
    handler._parsed_results = []
    buckets = handler.build_buckets()
    assert isinstance(buckets, dict)
    assert "organize" in buckets
    assert "download" in buckets
    assert "pending" in buckets
    for key in buckets:
        assert buckets[key] == [], f"桶 '{key}' 应为空列表"


@pytest.mark.e2e
def test_build_buckets_with_results(window, qtbot):
    """build_buckets: 有 next_action 的条目被正确分组。"""
    handler = window._core.query._summary

    items = [
        _make_parsed(number=1, next_action="archive", stage_status="archive_ready"),
        _make_parsed(number=2, next_action="download", stage_status="download_ready"),
        _make_parsed(number=3, next_action="expire", stage_status="expired"),
    ]
    handler._parsed_results = items
    buckets = handler.build_buckets()
    assert len(buckets["organize"]) == 1
    assert len(buckets["download"]) == 1
    assert len(buckets["expire"]) == 1
    assert len(buckets["not_found"]) == 0
