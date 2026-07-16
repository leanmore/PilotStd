# tests/gui/test_actions_flow_engine.py
"""ActionsFlowEngine 纯逻辑单元测试 — 不依赖 Qt，纯 pytest。

覆盖所有 4 个静态方法，目标覆盖率 ≥ 90%。
"""

from __future__ import annotations

import time as _time
from unittest.mock import patch

import pytest

from pilotstd.ui.core.handlers.actions_flow_engine import ActionsFlowEngine


@pytest.fixture
def engine():
    return ActionsFlowEngine()


# ════════════════════════════════════════════════════════════════
# get_toolbar_button_keys
# ════════════════════════════════════════════════════════════════


class TestGetToolbarButtonKeys:
    def test_returns_8_keys(self, engine):
        keys = engine.get_toolbar_button_keys()
        assert len(keys) == 8

    def test_all_start_with_btn(self, engine):
        keys = engine.get_toolbar_button_keys()
        for k in keys:
            assert k.startswith("btn_"), f"键名 '{k}' 应以 btn_ 开头"

    def test_contains_expected_keys(self, engine):
        keys = engine.get_toolbar_button_keys()
        expected = {"btn_select", "btn_query", "btn_download", "btn_normalize",
                    "btn_save", "btn_auto", "btn_announce", "btn_pause"}
        assert set(keys) == expected

    def test_returns_tuple(self, engine):
        assert isinstance(engine.get_toolbar_button_keys(), tuple)


# ════════════════════════════════════════════════════════════════
# is_update_throttled
# ════════════════════════════════════════════════════════════════


class TestIsUpdateThrottled:
    def test_int_timestamp_within_24h(self, engine):
        """1 小时前的时间戳 → 应节流。"""
        recent = _time.time() - 3600
        assert engine.is_update_throttled(recent) is True

    def test_float_timestamp_within_24h(self, engine):
        """30 分钟前 → 应节流。"""
        recent = _time.time() - 1800.0
        assert engine.is_update_throttled(recent) is True

    def test_old_timestamp_outside_24h(self, engine):
        """25 小时前 → 不应节流。"""
        old = _time.time() - 90000
        assert engine.is_update_throttled(old) is False

    def test_int_zero(self, engine):
        """0 时间戳 → 不应节流。"""
        assert engine.is_update_throttled(0) is False

    def test_non_numeric_type(self, engine):
        """非 int/float（如 str）→ 不应节流。"""
        assert engine.is_update_throttled("not_a_number") is False

    def test_none(self, engine):
        """None → 不应节流。"""
        assert engine.is_update_throttled(None) is False

    def test_negative_timestamp(self, engine):
        """负数时间戳 → 不应节流。"""
        assert engine.is_update_throttled(-1) is False

    def test_exactly_24h(self, engine):
        """恰好 24 小时临界点附近：86399 秒前（差 1 秒）→ 应在节流窗口内。"""
        boundary = _time.time() - 86399
        assert engine.is_update_throttled(boundary) is True


# ════════════════════════════════════════════════════════════════
# is_frozen
# ════════════════════════════════════════════════════════════════


class TestIsFrozen:
    def test_not_frozen_by_default(self, engine):
        """开发环境（sys.frozen 不存在或为 False）→ False。"""
        with patch("sys.frozen", False, create=True):
            assert engine.is_frozen() is False

    def test_frozen_when_true(self, engine):
        """PyInstaller exe 模式（sys.frozen=True）→ True。"""
        with patch("sys.frozen", True, create=True):
            assert engine.is_frozen() is True
