# tests/gui/test_query_summary_flow_engine.py
"""QuerySummaryFlowEngine 单元测试 — 纯 Python，不启动 QApplication。

覆盖 4 个静态方法的：正常路径、边界值、异常容错。
"""

from __future__ import annotations

from typing import Any

import pytest

from pilotstd.ui.core.handlers.query_summary_flow_engine import QuerySummaryFlowEngine


# ═══════════════════════════════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════════════════════════════


class _FakeStd:
    """最小 ParsedStdInfo 兼容对象。"""

    def __init__(
        self,
        next_action: str = "",
        stage_status: str = "",
        match_status: str = "",
        raw_filename: str = "",
        source_path: str = "",
        std_name: str = "",
    ):
        self.next_action = next_action
        self.stage_status = stage_status
        self.match_status = match_status
        self.raw_filename = raw_filename
        self.source_path = source_path
        self.std_name = std_name

    def get_full_number(self) -> str:
        return "GB/T 1-2020"


@pytest.fixture
def engine() -> QuerySummaryFlowEngine:
    return QuerySummaryFlowEngine()


# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════


class TestConstants:
    def test_bucket_names(self):
        assert "organize" in QuerySummaryFlowEngine.BUCKET_NAMES
        assert "pending" in QuerySummaryFlowEngine.BUCKET_NAMES
        assert "not_found" in QuerySummaryFlowEngine.BUCKET_NAMES
        assert len(QuerySummaryFlowEngine.BUCKET_NAMES) == 7

    def test_action_to_bucket(self):
        assert QuerySummaryFlowEngine.ACTION_TO_BUCKET["archive"] == "organize"
        assert QuerySummaryFlowEngine.ACTION_TO_BUCKET["download"] == "download"
        assert QuerySummaryFlowEngine.ACTION_TO_BUCKET["pending"] == "pending"

    def test_status_label_map(self):
        assert QuerySummaryFlowEngine.STATUS_LABEL_MAP["chain_exhausted"]
        assert QuerySummaryFlowEngine.STATUS_LABEL_MAP["name_conflict"]
        assert "unknown_key" not in QuerySummaryFlowEngine.STATUS_LABEL_MAP


# ═══════════════════════════════════════════════════════════════════
# build_buckets
# ═══════════════════════════════════════════════════════════════════


class TestBuildBuckets:
    def test_normal(self, engine):
        items = [
            _FakeStd(next_action="archive"),
            _FakeStd(next_action="archive"),
            _FakeStd(next_action="download"),
            _FakeStd(next_action="pending"),
            _FakeStd(next_action="expire"),
        ]
        buckets = engine.build_buckets(items)
        assert len(buckets["organize"]) == 2
        assert len(buckets["download"]) == 1
        assert len(buckets["pending"]) == 1
        assert len(buckets["expire"]) == 1
        assert len(buckets["not_found"]) == 0

    def test_empty_list(self, engine):
        buckets = engine.build_buckets([])
        for k in engine.BUCKET_NAMES:
            assert buckets[k] == []

    def test_none_list(self, engine):
        buckets = engine.build_buckets(None)  # type: ignore[arg-type]
        for k in engine.BUCKET_NAMES:
            assert buckets[k] == []

    def test_all_buckets_present(self, engine):
        buckets = engine.build_buckets([])
        assert set(buckets.keys()) == set(engine.BUCKET_NAMES)

    def test_unknown_action(self, engine):
        """未知 next_action 不归入任何桶。"""
        items = [
            _FakeStd(next_action="archive"),
            _FakeStd(next_action="unknown_bucket_type"),
        ]
        buckets = engine.build_buckets(items)
        assert len(buckets["organize"]) == 1
        # 未知 action 不出现
        total = sum(len(v) for v in buckets.values())
        assert total == 1

    def test_no_next_action_attr(self, engine):
        """无 next_action 属性的对象 → 不归入任何桶。"""

        class NoAction:
            pass

        items = [_FakeStd(next_action="archive"), NoAction()]  # type: ignore[list-item]
        buckets = engine.build_buckets(items)  # type: ignore[arg-type]
        assert len(buckets["organize"]) == 1
        total = sum(len(v) for v in buckets.values())
        assert total == 1

    def test_empty_next_action(self, engine):
        items = [_FakeStd(next_action="")]
        buckets = engine.build_buckets(items)
        total = sum(len(v) for v in buckets.values())
        assert total == 0

    def test_manual_download(self, engine):
        items = [_FakeStd(next_action="manual_download")] * 3
        buckets = engine.build_buckets(items)
        assert len(buckets["manual_download"]) == 3

    def test_not_found(self, engine):
        items = [_FakeStd(next_action="not_found")] * 5
        buckets = engine.build_buckets(items)
        assert len(buckets["not_found"]) == 5

    def test_large_list(self, engine):
        items = [_FakeStd(next_action="archive")] * 10000
        buckets = engine.build_buckets(items)
        assert len(buckets["organize"]) == 10000

    def test_returns_same_object_references(self, engine):
        items = [_FakeStd(next_action="archive")]
        buckets = engine.build_buckets(items)
        assert buckets["organize"][0] is items[0]


# ═══════════════════════════════════════════════════════════════════
# get_pending_reason
# ═══════════════════════════════════════════════════════════════════


class TestGetPendingReason:
    def test_known_status(self, engine):
        assert engine.get_pending_reason("chain_exhausted") == "所有适配器已尝试"

    def test_name_conflict(self, engine):
        assert engine.get_pending_reason("name_conflict") == "名称冲突"

    def test_unknown_status(self, engine):
        assert engine.get_pending_reason("unknown_reason") == ""

    def test_empty_string(self, engine):
        assert engine.get_pending_reason("") == ""

    def test_none(self, engine):
        assert engine.get_pending_reason(None) == ""  # type: ignore[arg-type]

    def test_int(self, engine):
        assert engine.get_pending_reason(123) == ""  # type: ignore[arg-type]

    def test_all_keys_have_labels(self, engine):
        for key in engine.STATUS_LABEL_MAP:
            assert engine.get_pending_reason(key), f"缺少: {key}"


# ═══════════════════════════════════════════════════════════════════
# safe_str
# ═══════════════════════════════════════════════════════════════════


class TestSafeStr:
    def test_normal_string(self, engine):
        assert engine.safe_str("hello") == "hello"

    def test_empty_string(self, engine):
        assert engine.safe_str("") == ""

    def test_none(self, engine):
        assert engine.safe_str(None) == ""

    def test_zero(self, engine):
        assert engine.safe_str(0) == ""

    def test_false_bool(self, engine):
        """False → ''，不是 'False'。"""
        assert engine.safe_str(False) == ""

    def test_true_bool(self, engine):
        """True → ''，不是 'True'。"""
        assert engine.safe_str(True) == ""

    def test_integer(self, engine):
        assert engine.safe_str(42) == "42"

    def test_float(self, engine):
        assert engine.safe_str(3.14) == "3.14"

    def test_list(self, engine):
        assert engine.safe_str([1, 2, 3]) == "[1, 2, 3]"


# ═══════════════════════════════════════════════════════════════════
# build_summary_message
# ═══════════════════════════════════════════════════════════════════


class TestBuildSummaryMessage:
    def test_normal(self, engine):
        buckets = {
            "organize": [1, 2, 3],
            "pending": [4],
            "expire": [5, 6],
            "download": [],
        }
        result = engine.build_summary_message(buckets, 100)
        assert "100" in result
        assert "3" in result
        assert "1" in result
        assert "2" in result

    def test_all_empty(self, engine):
        buckets = {k: [] for k in engine.BUCKET_NAMES}
        result = engine.build_summary_message(buckets, 0)
        assert "0 条" in result

    def test_missing_buckets(self, engine):
        result = engine.build_summary_message({}, 50)
        assert "50" in result
        assert "0 条" in result

    def test_none_buckets(self, engine):
        result = engine.build_summary_message(None, 10)  # type: ignore[arg-type]
        assert "10" in result

    def test_zero_total(self, engine):
        buckets = {"organize": [1]}
        result = engine.build_summary_message(buckets, 0)
        assert "0 条" in result

    def test_returns_string(self, engine):
        result = engine.build_summary_message({}, 5)
        assert isinstance(result, str)
        assert len(result) > 0
