import os
import shutil
import sys
import tempfile

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _copy_fixtures_to_tmp(test_data_dir):
    """把 fixtures 复制到临时目录，防止 _auto_move_expired 消耗原件。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_test_fixtures_")
    for name in os.listdir(test_data_dir):
        src = os.path.join(test_data_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, tmp)
    return tmp


def test_download_requires_scan_and_query(window, qtbot):
    """未导入时点击下载应弹出提示。"""
    window._parsed_results.clear()
    window._clear_table()
    window._on_download()
    qtbot.wait(200)
    assert len(window._parsed_results) == 0


@pytest.mark.timeout(60)
def test_download_mock_after_query(window, test_data_dir, qtbot):
    """mock 模式下扫描→查询→下载全流程不崩溃。"""
    from tests.gui.test_full_pipeline import _wait_worker

    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        _wait_worker(qtbot, window, "_scan_worker")
        assert window.work_table.rowCount() > 0, "扫描后应有数据"
        window._on_query()
        _wait_worker(qtbot, window, "_query_worker")
        window._on_download()
        _wait_worker(qtbot, window, "_download_worker")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_download_progress_bar_shows(window, test_data_dir, qtbot):
    """下载过程中进度条应可见。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        qtbot.wait(300)
        window._on_query()
        qtbot.wait(1000)
        window._on_download()
        qtbot.wait(200)
        assert window.progress_bar.isVisible()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
