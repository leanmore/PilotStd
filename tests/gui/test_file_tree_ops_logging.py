"""文件树驱动器就绪回调（体检 D-8 第 5 批，GUI 作业）。

`_on_drives_ready` 在 sip 不可用/树已析构时直接 return，原实现无任何痕迹。
本用例验证正常路径仍正确填充（日志路径由 debug 兜底，无法在无失效对象时触发）。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QTreeWidgetItem  # noqa: E402

from pilotstd.ui.main_window.parts import _file_tree_ops as ops  # noqa: E402


def test_on_drives_ready_populates_children(qapp) -> None:
    parent = QTreeWidgetItem(["This PC"])
    fake_self = SimpleNamespace(
        this_pc=parent,
        _drive_items={},
        _make_drive_item=lambda name, path: QTreeWidgetItem([name]),
    )

    ops._on_drives_ready(fake_self, [("C:", "C:\\")])

    assert parent.childCount() == 1
    assert fake_self._drive_items["C:\\"].text(0) == "C:"


def test_on_drives_ready_without_tree_returns(qapp) -> None:
    fake_self = SimpleNamespace(this_pc=None)
    ops._on_drives_ready(fake_self, [("C:", "C:\\")])  # 不应抛
