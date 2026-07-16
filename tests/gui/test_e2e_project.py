# tests/gui/test_e2e_project.py
"""E2E 测试 — ProjectHandler 冒烟。"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_project_restore_state_empty(window, qtbot):
    """restore_state: 空 state dict → 不崩溃。"""
    handler = window._core.project
    handler.restore_state({})
