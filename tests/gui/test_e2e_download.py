# tests/gui/test_e2e_download.py
"""E2E 测试 — DownloadUIHandler 核心路径。"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_filter_too_new_standards_empty(window, qtbot):
    """filter_too_new_standards 对空列表返回空 set。

    DownloadUIHandler 的完整 on_download 路径需要：
      - 扫描 → 查询 → 分类器 → download_list 填充
    在不模拟全管线的情况下，测试纯数据入口方法。
    """
    handler = window._core.download
    result = handler.filter_too_new_standards([])
    assert result == set()


@pytest.mark.e2e
def test_prepare_download_empty_guard(window, qtbot):
    """prepare_download：下载列表为空时触发前置对话框。

    _suppress_dialogs=True 时 stage_prereq 返回 "skip"，
    不在 ("run_prereq", "cancel") 中 → 返回 (True, [])。
    """
    handler = window._core.download
    ok, dl_list = handler.prepare_download()
    # _suppress_dialogs=True → "skip" → 通过 guard → (True, [])
    assert ok is True
    assert dl_list == []
