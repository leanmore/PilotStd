import os
import shutil
import sys
import tempfile

import pytest

from tests.gui.helpers import wait_for_worker_and_ui

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


@pytest.mark.timeout(60)
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
        wait_for_worker_and_ui(
            qtbot, window, "_scan_worker",
            ui_predicate=lambda: len(window._parsed_results) > 0,
        )
        assert len(window._parsed_results) > 0
        assert window.work_table.rowCount() > 0

        # 补充 std_name，跳过查询/规范化/存档的缺失名称弹窗
        for p in window._parsed_results:
            if not p.std_name:
                p.std_name = f"标准_{p.logical_code}_{p.number}"

        # 查询（后台线程）
        window._on_query()
        wait_for_worker_and_ui(
            qtbot, window, "_query_worker",
            ui_predicate=lambda: True,
        )

        # 下载（后台线程）
        window._on_download()
        wait_for_worker_and_ui(
            qtbot, window, "_download_worker",
            ui_predicate=lambda: True,
        )

        # 规范化（后台线程）
        window._on_normalize()
        wait_for_worker_and_ui(
            qtbot, window, "_normalize_worker",
            ui_predicate=lambda: True,
        )

        # 归档（后台线程）
        window._on_save_to_folder()
        from pilotstd.core.config import get_library_root

        wait_for_worker_and_ui(
            qtbot, window, "_archive_worker",
            ui_predicate=lambda: os.path.isdir(get_library_root(window._config)),
        )
        root = get_library_root(window._config)
        assert os.path.isdir(root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_auto_run_suppresses_dialogs(window, test_data_dir, qtbot):
    """自动运行模式应设置 _suppress_dialogs = True。"""
    assert window._suppress_dialogs is True


@pytest.mark.timeout(60)
def test_full_pipeline_no_exceptions(window, test_data_dir, qtbot):
    """全链路执行不应有未捕获异常。"""
    window._suppress_dialogs = True
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        wait_for_worker_and_ui(
            qtbot, window, "_scan_worker",
            ui_predicate=lambda: len(window._parsed_results) > 0,
        )
        window._on_query()
        wait_for_worker_and_ui(
            qtbot, window, "_query_worker",
            ui_predicate=lambda: True,
        )
        window._on_download()
        wait_for_worker_and_ui(
            qtbot, window, "_download_worker",
            ui_predicate=lambda: True,
        )
    except Exception as e:
        pytest.fail(f"全链路异常: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
