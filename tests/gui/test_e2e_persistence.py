# tests/gui/test_e2e_persistence.py
"""E2E 测试 — PersistenceHandler 核心路径。

PersistenceHandler 的 8 个方法均为纯配置读写 + QByteArray，
是所有 Handler 中可测性最高的。
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_window_geometry_roundtrip(window, qtbot):
    """窗口几何 save → restore 往返不崩溃。"""
    handler = window._core.persistence
    handler.save_window_geometry(window)
    handler.restore_window_geometry(window)


@pytest.mark.e2e
def test_splitter_sizes_roundtrip(window, qtbot):
    """分栏尺寸 save → restore 往返。"""
    handler = window._core.persistence
    handler.save_splitter_sizes(window._main_splitter, window._right_splitter)
    handler.restore_splitter_sizes(window._main_splitter, window._right_splitter)
