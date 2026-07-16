# tests/gui/test_query_flow_engine.py
"""QueryFlowEngine 纯逻辑单元测试 — 不依赖 Qt，纯 pytest。

覆盖所有 11 个方法，目标覆盖率 ≥ 90%。
"""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from pilotstd.models import ParsedStdInfo
from pilotstd.ui.core.handlers.query_flow_engine import QueryFlowEngine


# ── 测试辅助 ─────────────────────────────────────────────────


@dataclass
class _MockResult:
    """模拟 QueryResult 的最小字段集。"""
    standard_name: str = ""
    status: str = ""
    replaces: str = ""
    publish_date: str = ""
    implementation_date: str = ""
    responsible_dept: str = ""
    is_adopted: bool = False
    is_downloadable: bool = True
    source_site: str = "mock"


def _make_parsed(logical_code: str = "GB/T", number: int = 1, year: int = 2020) -> ParsedStdInfo:
    return ParsedStdInfo(
        raw_filename=f"{logical_code} {number}-{year}.pdf",
        logical_code=logical_code,
        number=number,
        year=year,
        std_name="测试标准",
    )


_SENTINEL = object()


def _make_parse_fn(returns=_SENTINEL):
    """创建可控的 parse_fn：接收 "标准号.pdf"，返回指定值或 ParsedStdInfo。"""
    def _parse(filename: str) -> Any:
        if returns == "raise":
            raise ValueError("模拟解析异常")
        if returns is None:
            return None
        if callable(returns):
            return returns(filename)
        return _make_parsed()

    if returns is _SENTINEL:
        # 默认：对任意输入都返回有效 ParsedStdInfo
        return _parse
    return _parse


# ── Fixture ───────────────────────────────────────────────────


@pytest.fixture
def engine():
    cfg = MagicMock()
    return QueryFlowEngine(cfg)


# ════════════════════════════════════════════════════════════════
# validate_standard
# ════════════════════════════════════════════════════════════════


class TestValidateStandard:
    def test_valid_standard(self, engine):
        assert engine.validate_standard("GB/T 1.1-2020") is True

    def test_empty_string(self, engine):
        assert engine.validate_standard("") is False

    def test_none_standard(self, engine):
        assert engine.validate_standard("") is False

    def test_whitespace_only(self, engine):
        assert engine.validate_standard("   ") is False

    def test_no_digit(self, engine):
        assert engine.validate_standard("ABC-DEF") is False

    def test_with_digit(self, engine):
        assert engine.validate_standard("ABC1") is True


# ════════════════════════════════════════════════════════════════
# determine_status_color
# ════════════════════════════════════════════════════════════════


class TestDetermineStatusColor:
    def test_current(self, engine):
        assert engine.determine_status_color("现行", True) == "#008000"

    def test_about_to_implement(self, engine):
        assert engine.determine_status_color("即将实施", True) == "#0000ff"

    def test_abolished(self, engine):
        assert engine.determine_status_color("废止", True) == "#ff0000"

    def test_abolished_variant(self, engine):
        assert engine.determine_status_color("已废止", True) == "#ff0000"

    def test_cancelled(self, engine):
        assert engine.determine_status_color("作废", True) == "#ff0000"

    def test_pending(self, engine):
        assert engine.determine_status_color("待确认", True) == "#808000"

    def test_unknown_status(self, engine):
        assert engine.determine_status_color("未知状态", True) == ""

    def test_current_not_downloadable(self, engine):
        assert engine.determine_status_color("现行", False) == "#808000"

    def test_about_to_implement_not_downloadable(self, engine):
        assert engine.determine_status_color("即将实施", False) == "#808000"

    def test_abolished_not_downloadable(self, engine):
        # 废止不受 is_downloadable 覆盖
        assert engine.determine_status_color("废止", False) == "#ff0000"

    def test_pending_not_downloadable(self, engine):
        # 待确认不受 is_downloadable 覆盖
        assert engine.determine_status_color("待确认", False) == "#808000"


# ════════════════════════════════════════════════════════════════
# build_result_cells
# ════════════════════════════════════════════════════════════════


class TestBuildResultCells:
    def test_normal_result(self, engine):
        result = _MockResult(
            standard_name="标准化导则",
            status="现行",
            replaces="GB/T 1.1-2009",
            publish_date="2020-03-06",
            implementation_date="2020-10-01",
            responsible_dept="全国标准化技术委员会",
            is_adopted=False,
            source_site="mock_query",
        )
        parsed = _make_parsed()
        cells = engine.build_result_cells(result, parsed, "mock_query")

        assert cells[0] == (1, "已查询(mock_query)")
        assert cells[1] == (3, "标准化导则")
        assert cells[2] == (4, "现行")
        assert cells[3] == (5, "GB/T 1.1-2009")
        assert cells[4] == (6, "2020-03-06")
        assert cells[5] == (7, "2020-10-01")
        assert cells[6] == (8, "全国标准化技术委员会")
        assert cells[7] == (9, "")

    def test_adopted_result(self, engine):
        result = _MockResult(is_adopted=True, source_site="ahbz")
        parsed = _make_parsed()
        cells = engine.build_result_cells(result, parsed, "ahbz")
        assert cells[7] == (9, "采标")

    def test_website_no_category_replaces(self, engine):
        result = _MockResult(replaces="网站无此分类", publish_date="网站无此分类",
                             implementation_date="网站无此分类",
                             responsible_dept="网站无此分类",
                             source_site="mock")
        parsed = _make_parsed()
        cells = engine.build_result_cells(result, parsed, "mock")
        assert cells[3] == (5, "")
        assert cells[4] == (6, "")
        assert cells[5] == (7, "")
        assert cells[6] == (8, "")

    def test_fallback_to_parsed_std_name(self, engine):
        result = _MockResult(standard_name="", source_site="mock")
        parsed = _make_parsed()
        parsed.std_name = "备选名称"
        cells = engine.build_result_cells(result, parsed, "mock")
        assert cells[1] == (3, "备选名称")


# ════════════════════════════════════════════════════════════════
# parse_csv_content
# ════════════════════════════════════════════════════════════════


class TestParseCsvContent:
    def test_valid_csv(self, engine, tmp_path):
        csv_path = tmp_path / "pending.csv"
        csv_path.write_text(
            "标准编号,标准名称\n"
            "GB/T 1.1-2020,标准化导则\n"
            "NB/T 47013-2021,无损检测\n",
            encoding="utf-8-sig",
        )
        parsed_list, failed = engine.parse_csv_content(str(csv_path), _make_parse_fn())
        assert len(parsed_list) == 2
        assert failed == []
        assert parsed_list[0].std_name == "标准化导则"
        assert parsed_list[1].std_name == "无损检测"

    def test_empty_csv(self, engine, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("", encoding="utf-8-sig")
        parsed_list, failed = engine.parse_csv_content(str(csv_path), _make_parse_fn())
        assert parsed_list == []
        assert failed == []

    def test_header_only_csv(self, engine, tmp_path):
        csv_path = tmp_path / "header_only.csv"
        csv_path.write_text("标准编号,标准名称\n", encoding="utf-8-sig")
        parsed_list, failed = engine.parse_csv_content(str(csv_path), _make_parse_fn())
        assert parsed_list == []
        assert failed == []

    def test_invalid_standard(self, engine, tmp_path):
        csv_path = tmp_path / "mixed.csv"
        csv_path.write_text(
            "标准编号,标准名称\n"
            "GB/T 1.1-2020,有效\n"
            "INVALID-!!,无效\n",
            encoding="utf-8-sig",
        )
        # 自定义 parse_fn：INVALID 标准返回 None
        def _selective_parse(filename: str) -> Any:
            if "INVALID" in filename:
                return None
            return _make_parsed()

        parsed_list, failed = engine.parse_csv_content(str(csv_path), _selective_parse)
        assert len(parsed_list) == 1  # 只有第一个有效
        assert "INVALID-!!" in failed

    def test_parse_fn_returns_none(self, engine, tmp_path):
        csv_path = tmp_path / "none.csv"
        csv_path.write_text(
            "标准编号,标准名称\n"
            "GB/T 1.1-2020,名称\n",
            encoding="utf-8-sig",
        )
        parsed_list, failed = engine.parse_csv_content(str(csv_path), _make_parse_fn(returns=None))
        assert parsed_list == []
        assert "GB/T 1.1-2020" in failed

    def test_parse_fn_raises_exception(self, engine, tmp_path):
        csv_path = tmp_path / "error.csv"
        csv_path.write_text(
            "标准编号,标准名称\n"
            "GB/T 1.1-2020,异常测试\n",
            encoding="utf-8-sig",
        )
        parsed_list, failed = engine.parse_csv_content(str(csv_path), _make_parse_fn(returns="raise"))
        assert parsed_list == []
        assert "GB/T 1.1-2020" in failed

    def test_skip_empty_lines(self, engine, tmp_path):
        csv_path = tmp_path / "with_gaps.csv"
        csv_path.write_text(
            "标准编号,标准名称\n"
            "GB/T 1.1-2020,有效\n"
            "\n"
            ",,\n"
            "NB/T 47013-2021,无损检测\n",
            encoding="utf-8-sig",
        )
        parsed_list, failed = engine.parse_csv_content(str(csv_path), _make_parse_fn())
        assert len(parsed_list) == 2

    def test_no_std_name_in_csv(self, engine, tmp_path):
        csv_path = tmp_path / "no_name.csv"
        csv_path.write_text(
            "标准编号,标准名称\n"
            "GB/T 1.1-2020,\n",
            encoding="utf-8-sig",
        )
        parsed_list, _ = engine.parse_csv_content(str(csv_path), _make_parse_fn())
        # CSV 中名称为空 → 保留 parsed 对象原有的 std_name（不回填空字符串覆盖）
        assert parsed_list[0].std_name == "测试标准"


# ════════════════════════════════════════════════════════════════
# filter_empty_standards
# ════════════════════════════════════════════════════════════════


class TestFilterEmptyStandards:
    def test_mixed(self, engine):
        result = engine.filter_empty_standards(["GB/T 1", "", "  ", "NB/T 2", None])  # type: ignore[arg-type]
        assert result == ["GB/T 1", "NB/T 2"]

    def test_all_valid(self, engine):
        assert engine.filter_empty_standards(["A", "B"]) == ["A", "B"]

    def test_all_empty(self, engine):
        assert engine.filter_empty_standards(["", "  "]) == []

    def test_empty_list(self, engine):
        assert engine.filter_empty_standards([]) == []


# ════════════════════════════════════════════════════════════════
# extract_year_from_std_number
# ════════════════════════════════════════════════════════════════


class TestExtractYear:
    def test_with_year(self, engine):
        assert engine.extract_year_from_std_number("GB/T 1.1-2020") == "2020"

    def test_en_dash(self, engine):
        assert engine.extract_year_from_std_number("ISO 9001–2015") == "2015"

    def test_no_year(self, engine):
        assert engine.extract_year_from_std_number("GB/T 1.1") == ""

    def test_year_not_at_end(self, engine):
        assert engine.extract_year_from_std_number("2020-GB/T") == ""

    def test_empty_string(self, engine):
        assert engine.extract_year_from_std_number("") == ""


# ════════════════════════════════════════════════════════════════
# build_pending_csv_row
# ════════════════════════════════════════════════════════════════


class TestBuildPendingCsvRow:
    def test_full_row(self, engine):
        row = {
            "standard_number": "GB/T 1.1-2020",
            "std_name": "标准化导则",
            "found_name": "Guides",
            "found_number": "GB/T 1.1",
            "effect_status": "现行",
            "score": 95,
            "source_site": "std_gov",
        }
        result = engine.build_pending_csv_row(row)
        assert result[0] == "GB/T 1.1-2020"
        assert result[1] == "标准化导则"
        assert result[2] == "Guides"
        assert result[3] == "2020"  # 年份提取
        assert result[4] == "GB/T 1.1"
        assert result[5] == "现行"
        assert result[6] == "95"

    def test_empty_row(self, engine):
        result = engine.build_pending_csv_row({})
        assert result == ["", "", "", "", "", "", "", ""]


# ════════════════════════════════════════════════════════════════
# build_pending_csv_headers
# ════════════════════════════════════════════════════════════════


class TestBuildPendingCsvHeaders:
    def test_returns_8_columns(self, engine):
        headers = engine.build_pending_csv_headers()
        assert len(headers) == 8

    def test_all_non_empty(self, engine):
        headers = engine.build_pending_csv_headers()
        assert all(h for h in headers)


# ════════════════════════════════════════════════════════════════
# deduplicate_standards
# ════════════════════════════════════════════════════════════════


class TestDeduplicateStandards:
    def test_with_duplicates(self, engine):
        result = engine.deduplicate_standards(["A", "B", "A", "C", "B"])
        assert result == ["A", "B", "C"]

    def test_no_duplicates(self, engine):
        assert engine.deduplicate_standards(["A", "B", "C"]) == ["A", "B", "C"]

    def test_empty_list(self, engine):
        assert engine.deduplicate_standards([]) == []

    def test_all_same(self, engine):
        assert engine.deduplicate_standards(["X", "X", "X"]) == ["X"]


# ════════════════════════════════════════════════════════════════
# batch_parse_standards
# ════════════════════════════════════════════════════════════════


class TestBatchParseStandards:
    def test_all_success(self, engine):
        results = engine.batch_parse_standards(
            ["GB/T 1.1-2020", "NB/T 47013-2021"], _make_parse_fn()
        )
        assert len(results) == 2
        assert results[0]["parsed"] is not None
        assert results[0]["error"] is None
        assert results[1]["parsed"] is not None
        assert results[1]["error"] is None

    def test_mixed_success_failure(self, engine):
        def _mixed_parse(filename: str) -> Any:
            if "INVALID" in filename:
                raise ValueError("bad")
            return _make_parsed()

        results = engine.batch_parse_standards(
            ["GB/T 1.1-2020", "INVALID", "NB/T 47013-2021"], _mixed_parse
        )
        assert len(results) == 3
        assert results[0]["error"] is None
        assert results[1]["error"] == "bad"
        assert results[2]["error"] is None

    def test_all_failure(self, engine):
        results = engine.batch_parse_standards(
            ["A", "B"], _make_parse_fn(returns="raise")
        )
        assert all(r["error"] is not None for r in results)

    def test_empty_list(self, engine):
        assert engine.batch_parse_standards([], _make_parse_fn()) == []

    def test_preserves_standard_string(self, engine):
        results = engine.batch_parse_standards(["GB/T 1.1-2020"], _make_parse_fn())
        assert results[0]["standard"] == "GB/T 1.1-2020"
