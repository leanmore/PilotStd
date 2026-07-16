# tests/gui/test_table_flow_engine.py
"""TableFlowEngine 单元测试 — 纯 Python，不启动 QApplication。"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.table_flow_engine import TableFlowEngine


@pytest.fixture
def engine() -> TableFlowEngine:
    return TableFlowEngine()


class _FakeObj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ═══════════════════════════════════════════════════════════════════
# row_get
# ═══════════════════════════════════════════════════════════════════


class TestRowGet:
    def test_dict(self, engine):
        assert engine.row_get({"a": "1", "b": "2"}, "a") == "1"

    def test_dict_missing_key(self, engine):
        assert engine.row_get({"a": "1"}, "b", "x") == "x"

    def test_dict_default(self, engine):
        assert engine.row_get({}, "any") == ""

    def test_object(self, engine):
        obj = _FakeObj(name="test", count=42)
        assert engine.row_get(obj, "name") == "test"

    def test_object_missing_attr(self, engine):
        obj = _FakeObj(name="test")
        assert engine.row_get(obj, "missing", "fallback") == "fallback"

    def test_int_value(self, engine):
        assert engine.row_get({"n": 42}, "n") == "42"


# ═══════════════════════════════════════════════════════════════════
# format_csv_row
# ═══════════════════════════════════════════════════════════════════


class TestFormatCsvRow:
    def test_normal(self, engine):
        row = {"a": "1", "b": "2", "c": "3"}
        assert engine.format_csv_row(row, ["a", "b", "c"]) == ["1", "2", "3"]

    def test_missing_keys(self, engine):
        row = {"a": "1"}
        assert engine.format_csv_row(row, ["a", "b", "c"]) == ["1", "", ""]

    def test_empty_row(self, engine):
        assert engine.format_csv_row({}, ["x", "y"]) == ["", ""]

    def test_empty_headers(self, engine):
        assert engine.format_csv_row({"a": "1"}, []) == []

    def test_reordered_headers(self, engine):
        row = {"a": "1", "b": "2"}
        assert engine.format_csv_row(row, ["b", "a"]) == ["2", "1"]


# ═══════════════════════════════════════════════════════════════════
# format_txt_row
# ═══════════════════════════════════════════════════════════════════


class TestFormatTxtRow:
    def test_normal(self, engine):
        row = {"a": "1", "b": "2"}
        assert engine.format_txt_row(row, ["a", "b"]) == "1\t2"

    def test_missing_keys(self, engine):
        row = {"a": "1"}
        assert engine.format_txt_row(row, ["a", "b"]) == "1\t"

    def test_empty(self, engine):
        assert engine.format_txt_row({}, []) == ""

    def test_single_column(self, engine):
        assert engine.format_txt_row({"x": "hello"}, ["x"]) == "hello"


# ═══════════════════════════════════════════════════════════════════
# validate_column_visibility
# ═══════════════════════════════════════════════════════════════════


class TestValidateColumnVisibility:
    def test_normal(self, engine):
        result = engine.validate_column_visibility([True, False, True], 3)
        assert result == [True, False, True]

    def test_none_returns_default(self, engine):
        result = engine.validate_column_visibility(None, 5)
        assert result == [True] * 5

    def test_empty_list_returns_default(self, engine):
        result = engine.validate_column_visibility([], 3)
        assert result == [True] * 3

    def test_shorter_than_col_count(self, engine):
        result = engine.validate_column_visibility([True, False], 5)
        assert len(result) == 5
        assert result[:2] == [True, False]
        assert result[2:] == [True, True, True]

    def test_longer_than_col_count(self, engine):
        result = engine.validate_column_visibility([True, False, True, False, True], 2)
        assert result == [True, False]

    def test_custom_default(self, engine):
        result = engine.validate_column_visibility(None, 3, [False, True, False])
        assert result == [False, True, False]

    def test_custom_default_partial_fill(self, engine):
        result = engine.validate_column_visibility([True], 3, [False, True, False])
        assert result == [True, True, False]
