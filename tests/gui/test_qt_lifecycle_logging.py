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


def test_is_qt_alive_without_sip(monkeypatch) -> None:
    """无 PyQt6/sip 时 `_sip_isdeleted()` 返回 None：应视为存活（体检 D-16）。"""
    from pilotstd.ui import qt_lifecycle

    monkeypatch.setattr(qt_lifecycle, "_sip_isdeleted", lambda: None)
    assert qt_lifecycle.is_qt_alive(object()) is True


def test_sip_isdeleted_import_error_returns_none(monkeypatch) -> None:
    """D-16：`from PyQt6 import sip` 抛 ImportError 时返回 None（原 pragma 排除的分支）。"""
    import builtins

    from pilotstd.ui import qt_lifecycle

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PyQt6" and fromlist and "sip" in fromlist:
            raise ImportError("simulated missing PyQt6.sip")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert qt_lifecycle._sip_isdeleted() is None
