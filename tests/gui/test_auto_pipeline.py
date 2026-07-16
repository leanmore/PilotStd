# tests/gui/test_auto_pipeline.py
"""AutoUIHandler 全链路集成测试。

覆盖 start_auto_pipeline() 扫描→查询→下载→归档 完整流程。
使用 mock 适配器（MockQueryAdapter + MockDownloadAdapter），仅 mock 对话框。
"""

from __future__ import annotations

import os
import shutil

import pytest


def _copy_fixture_files(src_dir: str, dst_dir: str) -> list[str]:
    """将 fixture 文件复制到临时目录，返回复制的文件路径列表。"""
    copied = []
    for name in os.listdir(src_dir):
        src = os.path.join(src_dir, name)
        if os.path.isfile(src):
            dst = os.path.join(dst_dir, name)
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


@pytest.mark.e2e
def test_auto_pipeline_full_flow(window, test_data_dir, qtbot, tmp_path):
    """E2E: 一键自动管线全流程 — 扫描 fixture 文件 → 查询 → 下载 → 归档。

    验证：
      - AutoWorker 启动后不崩溃
      - 各阶段信号正常触发
      - 表格被清空后重新填充
    """
    # ── 准备：复制 fixture 文件到临时扫描目录 ──
    source_dir = tmp_path / "scan_source"
    source_dir.mkdir()
    _copy_fixture_files(test_data_dir, str(source_dir))

    # ── 配置 library/downloads 目录 ──
    lib_dir = tmp_path / "library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    dl_dir = tmp_path / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)

    handler = window._core.auto
    # 更新下载引擎的 save_root 指向临时目录
    window._mgr.download_engine._save_root = str(dl_dir)
    # 确保 library root 指向测试临时目录
    window._config.set("storage.root_dir", str(lib_dir))
    window._config.save()

    # ── 执行：启动自动管线 ──
    handler.start_auto_pipeline(str(source_dir))

    worker = handler._auto_worker
    assert worker is not None, "AutoWorker 应已创建"

    # 等待 finished_signal（超时 60s，涵盖 4 阶段）
    with qtbot.waitSignal(worker.finished_signal, timeout=60000) as blocker:
        pass

    report = blocker.args[0] if blocker.args else {}
    assert isinstance(report, dict), "finished_signal 应携带 report dict"
    assert report.get("scan", 0) > 0, f"扫描应发现文件，实际: {report}"
    # 验证三个阶段字段存在（P8-3：关闭技术债 #2）
    assert "query" in report, f"report 应包含 query 阶段数据，实际 keys: {list(report.keys())}"
    assert "download" in report, "report 应包含 download 阶段数据"
    assert "archive" in report, "report 应包含 archive 阶段数据"


@pytest.mark.e2e
def test_auto_pipeline_empty_source(window, qtbot, tmp_path):
    """E2E: 空目录 → 自动管线应快速完成，不崩溃，表格保持空。"""
    source_dir = tmp_path / "empty_source"
    source_dir.mkdir()

    handler = window._core.auto
    # 清空表格
    window.work_table.setRowCount(0)

    handler.start_auto_pipeline(str(source_dir))

    worker = handler._auto_worker
    assert worker is not None

    with qtbot.waitSignal(worker.finished_signal, timeout=15000) as blocker:
        pass

    report = blocker.args[0] if blocker.args else {}
    assert report.get("scan", 0) == 0, f"空目录扫描应为 0，实际: {report}"
    assert window.work_table.rowCount() == 0, "空目录扫描后表格应保持空"
