import os
import shutil
import sys
import tempfile

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _wait_worker(qtbot, window, attr, timeout=30000):
    """等待 Worker 线程完成（兼容新旧 Handler 架构）。"""
    w = getattr(window, attr, None)
    if w is None and hasattr(window, "_core"):
        _worker_handler_map = {
            "_scan_worker": "scan",
            "_query_worker": "query",
            "_download_worker": "download",
            "_normalize_worker": "archive",
            "_archive_worker": "archive",
        }
        handler_name = _worker_handler_map.get(attr, attr.replace("_worker", ""))
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


def test_organize_requires_scan(window, qtbot):
    """未导入时点击规范化应弹出提示。"""
    window._parsed_results.clear()
    window._clear_table()
    window._on_normalize()
    qtbot.wait(200)
    assert window.work_table.rowCount() == 0


def test_normalize_generates_standard_names(window, test_data_dir, qtbot):
    """扫描后补全 std_name 再规范化，验证流程可执行。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        _wait_worker(qtbot, window, "_scan_worker")
        # 补充 std_name，跳过 normalize 的「缺失名称→查询」弹窗
        for p in window._parsed_results:
            if not p.std_name:
                p.std_name = f"标准_{p.logical_code}_{p.number}"
        window._on_normalize()
        _wait_worker(qtbot, window, "_normalize_worker")
        table = window.work_table
        assert table.rowCount() > 0
        for row in range(table.rowCount()):
            item = table.item(row, 3)
            assert item is not None
            assert len(item.text()) > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_save_to_folder_creates_files(window, test_data_dir, qtbot):
    """扫描→查询→存档后，文件应出现在 library 目录中。"""
    tmp_fixtures = tempfile.mkdtemp(prefix="pilotstd_test_fixtures_")
    try:
        for name in os.listdir(test_data_dir):
            src = os.path.join(test_data_dir, name)
            if os.path.isfile(src):
                shutil.copy2(src, tmp_fixtures)

        window._run_scan(tmp_fixtures)
        _wait_worker(qtbot, window, "_scan_worker")
        # 补充 std_name，跳过查询和存档的缺失名称弹窗
        for p in window._parsed_results:
            if not p.std_name:
                p.std_name = f"标准_{p.logical_code}_{p.number}"
        window._on_save_to_folder()
        _wait_worker(qtbot, window, "_archive_worker")
        from pilotstd.core.config import get_library_root

        root = get_library_root(window._config)
        assert os.path.isdir(root), f"标准库根目录应存在: {root}"
    finally:
        shutil.rmtree(tmp_fixtures, ignore_errors=True)
