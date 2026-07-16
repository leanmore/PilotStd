# tests/gui/test_e2e_export.py
"""E2E 测试 — ExportHandler 冒烟。"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_export_handler_collect_tree(window, qtbot):
    """_collect_folder_tree: 对不存在的路径静默返回空。"""
    handler = window._core.export
    lines: list[str] = []
    handler._collect_folder_tree("/nonexistent/mock/path", lines, "")
    # 方法总是追加 root 的 basename 到 lines
    assert len(lines) == 1
    assert "path" in lines[0]
