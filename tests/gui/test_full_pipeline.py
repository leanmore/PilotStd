import os
import shutil
import sys
import tempfile

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _wait_worker(qtbot, window, attr, timeout=30000):
    """等待 Worker 线程完成（兼容新旧 Handler 架构）。"""
    w = getattr(window, attr, None)
    # 新架构：worker 在 window._core.<handler>.<attr> 下
    if w is None and hasattr(window, "_core"):
        # attr → handler 映射：_scan_worker → scan, _query_worker → query, etc.
        handler_name = attr.replace("_worker", "")
        handler = getattr(window._core, handler_name, None)
        if handler is not None:
            w = getattr(handler, attr, None)
    if w is not None and w.isRunning():
        with qtbot.waitSignal(w.finished_signal, timeout=timeout):
            pass


def _copy_fixtures_to_tmp(test_data_dir):
    """把 fixtures 复制到临时目录，防止 _auto_move_expired 消耗原件。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_test_fixtures_")
    for name in os.listdir(test_data_dir):
        src = os.path.join(test_data_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, tmp)
    return tmp


def test_full_pipeline_scan_query_download(window, test_data_dir, qtbot):
    """完整链路：扫描→查询→下载→规范化→存档，mock 模式下不抛异常。"""
    window._suppress_dialogs = True
    tmp = tempfile.mkdtemp(prefix="pilotstd_full_pipeline_")
    try:
        for name in os.listdir(test_data_dir):
            src = os.path.join(test_data_dir, name)
            if os.path.isfile(src):
                shutil.copy2(src, tmp)

        # 扫描（后台线程）
        window._run_scan(tmp)
        _wait_worker(qtbot, window, "_scan_worker")
        assert len(window._parsed_results) > 0
        assert window.work_table.rowCount() > 0

        # 查询（后台线程）
        window._on_query()
        _wait_worker(qtbot, window, "_query_worker")

        # 下载（后台线程）
        window._on_download()
        _wait_worker(qtbot, window, "_download_worker")

        # 规范化（后台线程）
        window._on_normalize()
        _wait_worker(qtbot, window, "_normalize_worker")

        # 归档（后台线程）
        window._on_save_to_folder()
        _wait_worker(qtbot, window, "_archive_worker")
        root = window._get_library_root()
        assert os.path.isdir(root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_auto_run_suppresses_dialogs(window, test_data_dir, qtbot):
    """自动运行模式应设置 _suppress_dialogs = True。"""
    assert window._suppress_dialogs is True


def test_full_pipeline_no_exceptions(window, test_data_dir, qtbot):
    """全链路执行不应有未捕获异常。"""
    window._suppress_dialogs = True
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        _wait_worker(qtbot, window, "_scan_worker")
        window._on_query()
        _wait_worker(qtbot, window, "_query_worker")
        window._on_download()
        _wait_worker(qtbot, window, "_download_worker")
    except Exception as e:
        pytest.fail(f"全链路异常: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
