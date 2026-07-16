# tests/gui/test_table_helper_flow_engine.py
"""TableHelperFlowEngine 单元测试 — 纯 Python，不启动 QApplication。"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.table_helper_flow_engine import TableHelperFlowEngine


@pytest.fixture
def engine() -> TableHelperFlowEngine:
    return TableHelperFlowEngine()


class TestEnforceMinColumnWidth:
    def test_normal(self, engine):
        assert engine.enforce_min_column_width(200, 100) == 200

    def test_below_min(self, engine):
        assert engine.enforce_min_column_width(50, 100) == 100

    def test_equal(self, engine):
        assert engine.enforce_min_column_width(100, 100) == 100

    def test_zero_width(self, engine):
        assert engine.enforce_min_column_width(0, 50) == 50

    def test_zero_min(self, engine):
        assert engine.enforce_min_column_width(10, 0) == 10

    def test_negative_width(self, engine):
        assert engine.enforce_min_column_width(-10, 50) == 50

    def test_both_negative(self, engine):
        assert engine.enforce_min_column_width(-10, -5) == -5

    def test_large_values(self, engine):
        assert engine.enforce_min_column_width(9999, 10000) == 10000


class TestFindRowBySeq:
    def test_normal(self, engine):
        rows = [{"seq": 1}, {"seq": 2}, {"seq": 3}]
        assert engine.find_row_by_seq(rows, 2) == 1

    def test_not_found(self, engine):
        rows = [{"seq": 1}, {"seq": 2}]
        assert engine.find_row_by_seq(rows, 999) == -1

    def test_empty_list(self, engine):
        assert engine.find_row_by_seq([], 1) == -1

    def test_none_list(self, engine):
        assert engine.find_row_by_seq(None, 1) == -1  # type: ignore[arg-type]

    def test_first_row(self, engine):
        rows = [{"seq": 10}, {"seq": 20}]
        assert engine.find_row_by_seq(rows, 10) == 0

    def test_last_row(self, engine):
        rows = [{"seq": 10}, {"seq": 20}, {"seq": 30}]
        assert engine.find_row_by_seq(rows, 30) == 2

    def test_string_seq(self, engine):
        rows = [{"seq": "1"}, {"seq": "2"}]
        assert engine.find_row_by_seq(rows, 2) == 1

    def test_non_dict_rows_skipped(self, engine):
        rows = [{"seq": 1}, "not_a_dict", {"seq": 3}]  # type: ignore[list-item]
        assert engine.find_row_by_seq(rows, 3) == 2

    def test_missing_seq_key(self, engine):
        rows = [{"name": "a"}, {"seq": 2}]
        assert engine.find_row_by_seq(rows, 2) == 1

    def test_invalid_seq_value(self, engine):
        rows = [{"seq": "abc"}, {"seq": 2}]
        assert engine.find_row_by_seq(rows, 2) == 1

    def test_hash_key_fallback(self, engine):
        rows = [{"#": "1"}, {"#": "2"}]
        assert engine.find_row_by_seq(rows, 2) == 1
