"""欢迎对话框 should_skip 的 bool 契约（D-17 mypy 收窄回归，GUI 作业）。"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


def test_should_skip_returns_bool(qapp) -> None:
    from pilotstd.ui.welcome_dialog import WelcomeDialog

    dialog = WelcomeDialog()
    dialog.skip_cb.setChecked(True)
    assert dialog.should_skip() is True
    dialog.skip_cb.setChecked(False)
    assert dialog.should_skip() is False
