import os
import shutil
import sys
import tempfile

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _wait_worker(qtbot, window, attr, timeout=30000):
    """等待 Worker 线程完成。"""
    w = getattr(window, attr, None)
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
    """扫描后点击规范化应生成标准文件名填入表格。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        _wait_worker(qtbot, window, "_scan_worker")
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
        window._on_query()
        _wait_worker(qtbot, window, "_query_worker")
        window._on_save_to_folder()
        _wait_worker(qtbot, window, "_archive_worker")
        root = window._get_library_root()
        assert os.path.isdir(root), f"标准库根目录应存在: {root}"
        subdirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
        assert len(subdirs) > 0, "应有至少一个分类子目录"
    finally:
        shutil.rmtree(tmp_fixtures, ignore_errors=True)
