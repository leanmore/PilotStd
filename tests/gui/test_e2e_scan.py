# tests/gui/test_e2e_scan.py
"""E2E 测试 — ScanUIHandler.run_scan 核心路径。"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest
from PyQt6.QtWidgets import QApplication


def _copy_fixtures_to_tmp(test_data_dir: str) -> str:
    tmp = tempfile.mkdtemp(prefix="pilotstd_e2e_scan_")
    for name in os.listdir(test_data_dir):
        src = os.path.join(test_data_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, tmp)
    return tmp


@pytest.mark.e2e
def test_run_scan_populates_table(window, test_data_dir, qtbot):
    """E2E: 扫描 fixture 文件 → 表格填充 '已扫描' 行。

    覆盖 ScanUIHandler.run_scan() 的目录扫描路径：
      - _scan_directory → ScanWorker 创建 + 信号连接
      - on_scan_batch_ready → 表格行追加
      - on_scan_finished → 统计汇总
    """
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        handler = window._core.scan
        handler.run_scan(tmp)

        # 等待 ScanWorker 完成 + 处理剩余队列信号
        worker = handler._scan_worker
        if worker is not None:
            qtbot.waitUntil(lambda: not worker.isRunning(), timeout=10000)
        QApplication.processEvents()

        table = window.work_table
        assert table.rowCount() > 0, "扫描后表格应有数据行"

        found_scanned = False
        for row in range(table.rowCount()):
            item = table.item(row, 1)  # col1 = 工作状态
            if item and "扫描" in item.text():
                found_scanned = True
                break
        assert found_scanned, "至少一行应显示'已扫描'状态"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.e2e
def test_run_scan_single_file(window, test_data_dir, qtbot):
    """E2E: 扫描单个 PDF 文件 → 解析 + 表格填充 1 行。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_e2e_scan_single_")
    # 复制 fixtures 中的一个 PDF 作为单文件测试
    fixture_pdf = os.path.join(test_data_dir, "GBT 1.1-2020.pdf")
    single_pdf = os.path.join(tmp, "GBT 1.1-2020.pdf")
    shutil.copy2(fixture_pdf, single_pdf)
    try:
        handler = window._core.scan
        handler.run_scan(single_pdf)

        table = window.work_table
        assert table.rowCount() > 0, f"单文件扫描应有结果，实际行数={table.rowCount()}"

        status_item = table.item(0, 1)
        assert status_item is not None
        assert "扫描" in status_item.text(), f"状态应含'扫描', 实际='{status_item.text()}'"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
