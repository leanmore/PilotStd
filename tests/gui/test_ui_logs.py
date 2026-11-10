# tests/gui/test_ui_logs.py — U-3/U-4 批 3 的 UI 两条日志升级
"""UI 日志升级：下载 CSV 解析、导出目录树 scandir 失败必须 WARNING。

放在 tests/gui/：backend job 不安装 PyQt6，根目录测试不得 import
pilotstd.ui；G-029 也要求 UI 变更的测试落在 tests/gui/。
"""

import logging

import pytest

pytest.importorskip("PyQt6")

from pilotstd.ui.core.handlers.download_flow_engine import DownloadFlowEngine
from pilotstd.ui.main_window.parts import _export_ops


def test_download_csv_parse_failure_warns(monkeypatch, caplog) -> None:
    """下载 CSV 解析失败 → WARNING + []。"""
    import csv as csv_mod

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("bad csv")

    # 该函数在体内 `import csv`，故 patch 全局 csv.DictReader（同一模块对象）
    monkeypatch.setattr(csv_mod, "DictReader", _boom)
    with caplog.at_level(logging.WARNING, logger="pilotstd.ui.core.handlers.download_flow_engine"):
        assert DownloadFlowEngine.parse_download_csv("standard_number\nGB 1\n") == []

    assert any("下载 CSV 解析失败" in r.message for r in caplog.records)


def test_export_folder_tree_scan_failure_warns(tmp_path, monkeypatch, caplog) -> None:
    """导出目录树 scandir 无权限 → WARNING（导出内容被截断可见）。"""

    def _boom(path):
        raise PermissionError("denied")

    monkeypatch.setattr(_export_ops.os, "scandir", _boom)
    lines: list = []
    with caplog.at_level(logging.WARNING, logger="pilotstd.ui"):
        _export_ops._collect_folder_tree(None, str(tmp_path), lines, "", 0)

    assert any("导出失败" in r.message for r in caplog.records)
