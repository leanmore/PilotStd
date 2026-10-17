"""Qt 生命周期失败可见性（体检 D-8 第 3 批，仅 GUI 作业）。

`pilotstd.ui` 包在导入时即加载 PyQt6，故该用例不能放后端测试作业
（CI run 1058 实测：ModuleNotFoundError: No module named 'PyQt6'）。
"""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("PyQt6")


def test_forget_orphan_not_registered_logs(caplog) -> None:
    from pilotstd.ui import qt_lifecycle

    with caplog.at_level(logging.DEBUG, logger="pilotstd.ui.qt_lifecycle"):
        qt_lifecycle._forget_orphan(object())
    assert "orphan worker not in registry" in caplog.text
