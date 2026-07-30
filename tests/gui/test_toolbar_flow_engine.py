# tests/gui/test_toolbar_flow_engine.py
"""ToolbarFlowEngine 单元测试 — 纯 Python，不启动 QApplication。

覆盖 3 个静态方法的全分支 + 边界 + 安全降级。
"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.toolbar_flow_engine import ToolbarFlowEngine


@pytest.fixture
def engine() -> ToolbarFlowEngine:
    return ToolbarFlowEngine()


class TestComputeButtonState:
    def test_basic_enabled(self, engine):
        rule = {"min_selection": 1, "max_selection": None, "hide_when_running": False}
        result = engine.compute_button_state(2, False, rule)
        assert result == {"enabled": True, "visible": True}

    def test_below_min_disabled(self, engine):
        rule = {"min_selection": 1}
        result = engine.compute_button_state(0, False, rule)
        assert result["enabled"] is False

    def test_above_max_disabled(self, engine):
        rule = {"min_selection": 0, "max_selection": 3}
        result = engine.compute_button_state(5, False, rule)
        assert result["enabled"] is False

    def test_hidden_when_running(self, engine):
        """运行中隐藏：visible=False，但 enabled 不受影响。"""
        rule = {"min_selection": 0, "hide_when_running": True}
        result = engine.compute_button_state(1, True, rule)
        assert result["visible"] is False
        assert result["enabled"] is True

    def test_visible_when_not_running(self, engine):
        rule = {"hide_when_running": True}
        result = engine.compute_button_state(0, False, rule)
        assert result["visible"] is True

    def test_empty_rule_defaults(self, engine):
        """空规则：默认启用+可见。"""
        result = engine.compute_button_state(0, False, {})
        assert result == {"enabled": True, "visible": True}


class TestMergeToolbarStates:
    def test_any_enabled(self, engine):
        states = [{"enabled": False, "visible": True}, {"enabled": True, "visible": False}]
        result = engine.merge_toolbar_states(states)
        assert result == {"toolbar_enabled": True, "toolbar_visible": True}

    def test_all_disabled(self, engine):
        states = [{"enabled": False, "visible": False}] * 3
        result = engine.merge_toolbar_states(states)
        assert result == {"toolbar_enabled": False, "toolbar_visible": False}

    def test_empty_list(self, engine):
        result = engine.merge_toolbar_states([])
        assert result == {"toolbar_enabled": False, "toolbar_visible": False}


class TestResolveActionGroup:
    def test_known_mode(self, engine):
        mapping = {"edit": ["save", "undo"], "view": ["zoom_in"]}
        assert engine.resolve_action_group("edit", mapping) == ["save", "undo"]

    def test_unknown_mode_returns_empty(self, engine):
        """未知模式安全降级，返回空列表不抛异常。"""
        mapping = {"edit": ["save"]}
        assert engine.resolve_action_group("unknown", mapping) == []

    def test_empty_mapping(self, engine):
        assert engine.resolve_action_group("edit", {}) == []
