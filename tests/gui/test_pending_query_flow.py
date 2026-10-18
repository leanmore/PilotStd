"""D-16：`_do_pending_query` 的提示/取消路径（此前该段被 pragma 排除）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6")


def _fake_self(parsed: list, failed: list, reply):
    return SimpleNamespace(
        _mgr_ready=True,
        _parsed_results=[],
        _parse_pending_csv=lambda path: (parsed, failed),
        _question_dlg=lambda title, msg: reply,
        status_changed=type("Sig", (), {"emit": lambda self, msg: None})(),
    )


def test_do_pending_query_returns_when_manager_not_ready(qapp) -> None:
    from pilotstd.ui.main_window.parts._query_ops import _do_pending_query

    fake = _fake_self([], [], None)
    fake._mgr_ready = False
    _do_pending_query(fake)  # 不抛即可


def test_do_pending_query_cancel_after_parse(qapp, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from pilotstd.ui.main_window.parts import _query_ops as ops

    monkeypatch.setattr(ops.QFileDialog, "getOpenFileName", lambda *a, **k: ("/tmp/pending.csv", ""))
    fake = _fake_self([object()], ["未识别.pdf"], QMessageBox.StandardButton.No)

    ops._do_pending_query(fake)  # 覆盖 msg 拼装 + 用户取消分支


def test_do_pending_query_returns_when_no_parsed(qapp, monkeypatch) -> None:
    from pilotstd.ui.main_window.parts import _query_ops as ops

    monkeypatch.setattr(ops.QFileDialog, "getOpenFileName", lambda *a, **k: ("/tmp/pending.csv", ""))
    warnings: list[str] = []
    monkeypatch.setattr(ops.QMessageBox, "warning", lambda *a, **k: warnings.append("warn"))

    ops._do_pending_query(_fake_self([], [], None))
    assert warnings == ["warn"]
