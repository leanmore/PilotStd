# tests/gui/test_e2e_file_dialog.py
"""E2E 测试 — FileDialogHandler 冒烟。

pick_folder 依赖 QFileDialog.getExistingDirectory，
pywinauto 模式下不做 patch，需要显式 monkeypatch 避免阻塞。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_pick_folder_returns_path(window, qtbot, monkeypatch):
    """pick_folder: monkeypatch QFileDialog → 返回模拟路径。"""
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda parent, title, start_dir: "/mock/selected/dir",
    )
    handler = window._core.file_dialog
    path = handler.pick_folder("选择文件夹")
    assert path == "/mock/selected/dir"
