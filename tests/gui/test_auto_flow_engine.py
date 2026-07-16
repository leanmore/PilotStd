# tests/gui/test_auto_flow_engine.py
"""AutoFlowEngine 纯单元测试 — 零 Qt 依赖，毫秒级。"""

from __future__ import annotations

from pilotstd.ui.core.handlers.auto_flow_engine import AutoFlowEngine


class _FakeResult:
    """模拟查询结果对象。"""

    def __init__(self, std_name: str, effect_status: str, is_adopted: bool, number: str = ""):
        self.std_name = std_name
        self.effect_status = effect_status
        self.is_adopted = is_adopted
        self._number = number

    def get_full_number(self) -> str:
        return self._number


class TestAutoFlowEngine:
    """AutoFlowEngine.build_summary_stats 纯逻辑测试。"""

    def test_empty_results(self):
        stats = AutoFlowEngine.build_summary_stats([])
        assert stats["total"] == 0
        assert stats["not_found_count"] == 0
        assert stats["expired_count"] == 0
        assert stats["adopted_count"] == 0
        assert stats["found_count"] == 0
        assert stats["manual_all"] == []

    def test_all_found_valid(self):
        results = [
            _FakeResult("GB/T 1.1", "现行", False, "GB/T 1.1-2020"),
            _FakeResult("GB/T 1.2", "现行", False, "GB/T 1.2-2020"),
        ]
        stats = AutoFlowEngine.build_summary_stats(results)
        assert stats["total"] == 2
        assert stats["found_count"] == 2
        assert stats["not_found_count"] == 0
        assert stats["expired_count"] == 0
        assert stats["adopted_count"] == 0
        assert stats["manual_all"] == []

    def test_not_found_detected(self):
        results = [
            _FakeResult("GB/T 1.1", "现行", False, "GB/T 1.1"),
            _FakeResult("", "现行", False, "GB/T 1.2"),
        ]
        stats = AutoFlowEngine.build_summary_stats(results)
        assert stats["total"] == 2
        assert stats["found_count"] == 1
        assert stats["not_found_count"] == 1
        assert len(stats["manual_all"]) == 1
        assert stats["manual_all"][0]["reason"] == "not_found"
        assert stats["manual_all"][0]["number"] == "GB/T 1.2"

    def test_expired_detected(self):
        results = [
            _FakeResult("GB/T 1.1", "废止", False, "GB/T 1.1"),
            _FakeResult("GB/T 1.2", "已废止", False, "GB/T 1.2"),
            _FakeResult("GB/T 1.3", "作废", False, "GB/T 1.3"),
            _FakeResult("GB/T 1.4", "现行", False, "GB/T 1.4"),
        ]
        stats = AutoFlowEngine.build_summary_stats(results)
        assert stats["total"] == 4
        assert stats["expired_count"] == 3

    def test_adopted_detected(self):
        results = [
            _FakeResult("GB/T 1.1", "现行", True, "GB/T 1.1"),
            _FakeResult("GB/T 1.2", "现行", False, "GB/T 1.2"),
        ]
        stats = AutoFlowEngine.build_summary_stats(results)
        assert stats["adopted_count"] == 1
        assert len(stats["manual_all"]) == 1
        assert stats["manual_all"][0]["reason"] == "adopted"

    def test_mixed_results(self):
        results = [
            _FakeResult("GB/T 1.1", "现行", False, "GB/T 1.1"),
            _FakeResult("", "现行", False, "GB/T 1.2"),
            _FakeResult("GB/T 1.3", "废止", False, "GB/T 1.3"),
            _FakeResult("GB/T 1.4", "现行", True, "GB/T 1.4"),
            _FakeResult("GB/T 1.5", "现行", False, "GB/T 1.5"),
        ]
        stats = AutoFlowEngine.build_summary_stats(results)
        assert stats["total"] == 5
        assert stats["found_count"] == 4
        assert stats["not_found_count"] == 1
        assert stats["expired_count"] == 1
        assert stats["adopted_count"] == 1
        assert len(stats["manual_all"]) == 2  # not_found + adopted
        reasons = [m["reason"] for m in stats["manual_all"]]
        assert "not_found" in reasons
        assert "adopted" in reasons

    def test_none_results_handled(self):
        stats = AutoFlowEngine.build_summary_stats(None)
        assert stats["total"] == 0
        assert stats["manual_all"] == []
