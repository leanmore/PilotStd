# tests/gui/test_e2e_announce.py
"""E2E 测试 — AnnounceUIHandler.check_guard 核心路径。"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_check_guard_returns_true_when_enabled(window, qtbot):
    """check_guard: use_announcement_match=False → 返回 True（可继续）。

    mock_main_window 默认设置 use_announcement_match=False。
    """
    window._config.set("query.use_announcement_match", False)
    handler = window._core.announce
    assert handler.check_guard() is True


@pytest.mark.e2e
def test_check_guard_returns_false_when_disabled(window, qtbot):
    """check_guard: use_announcement_match=True → 弹窗 + 返回 False。

    Web 缓存模式启用时，本地公告检查被禁用。
    """
    window._config.set("query.use_announcement_match", True)
    handler = window._core.announce
    # QMessageBox.information 已被 conftest monkeypatch 为返回 Ok
    result = handler.check_guard()
    assert result is False
