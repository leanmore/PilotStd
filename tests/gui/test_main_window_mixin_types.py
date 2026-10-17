"""D-17 收口回归：main_window 类型收窄不得改变运行时行为（GUI 作业）。

- `_WindowLifecycleMixin` 的 QMainWindow 基类只在 TYPE_CHECKING 期存在，运行时须仍是 object；
- `_add_action` 收窄 `QMenu.addAction` 的 Optional，实际必须返回 QAction。
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


def test_lifecycle_mixin_runtime_base_is_object(qapp) -> None:
    from pilotstd.ui.main_window._window_lifecycle import _WindowLifecycleMixin

    assert _WindowLifecycleMixin.__mro__[1] is object


def test_add_action_returns_action(qapp) -> None:
    from PyQt6.QtWidgets import QMenu

    from pilotstd.ui.main_window.parts._table_ops import _add_action

    menu = QMenu()
    action = _add_action(menu, "测试动作")
    assert action is not None
    assert action.text() == "测试动作"


def test_pick_folder_normalizes_non_str(qapp, monkeypatch) -> None:
    from pilotstd.ui.main_window.parts import _file_dialog_ops as ops

    monkeypatch.setattr(ops.QFileDialog, "getExistingDirectory", lambda *a, **k: "/tmp/x")
    assert ops._pick_folder(object(), "标题") == "/tmp/x"

    monkeypatch.setattr(ops.QFileDialog, "getExistingDirectory", lambda *a, **k: None)
    assert ops._pick_folder(object(), "标题") == ""


def test_confirm_update_returns_bool(qapp, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from pilotstd.ui.main_window.parts import _actions_ops as ops

    monkeypatch.setattr(ops.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    release = {"tag_name": "v2.0.0", "body": "notes"}
    assert ops._confirm_update_available(object(), "v1.0.0", release) is True

    monkeypatch.setattr(ops.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    assert ops._confirm_update_available(object(), "v1.0.0", release) is False
