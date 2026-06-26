# tests/gui/test_scan.py
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _wait_scan(qtbot, window, timeout=5000):
    """等待 ScanWorker 完成。"""
    w = getattr(window, "_scan_worker", None)
    if w is not None and w.isRunning():
        with qtbot.waitSignal(w.finished_signal, timeout=timeout):
            pass


def test_scan_directory_populates_table(window, test_data_dir, qtbot):
    """扫描 fixtures 目录后表格应有行数据。"""
    window._run_scan(test_data_dir)
    _wait_scan(qtbot, window)
    table = window.work_table
    assert table.rowCount() > 0, "扫描后表格应有行"


def test_scan_parses_standard_numbers(window, test_data_dir, qtbot):
    """扫描后 _parsed_results 应含解析出的标准信息。"""
    window._run_scan(test_data_dir)
    _wait_scan(qtbot, window)
    parsed = window._parsed_results
    assert len(parsed) > 0
    numbers = [p.number for p in parsed]
    assert 1 in numbers
    assert 67890 in numbers
    assert 47013 in numbers


def test_scan_success_count(window, test_data_dir, qtbot):
    """扫描结果数正确（5 个文件中 4 个可识别标准号，readme.txt 不可识别）。"""
    window._run_scan(test_data_dir)
    _wait_scan(qtbot, window)
    parsed = window._parsed_results
    filenames = [os.path.basename(p.source_path) if p.source_path else "" for p in parsed]
    assert "readme.txt" not in filenames
    assert len(parsed) == 4


def test_scan_shows_status_message(window, test_data_dir, qtbot):
    """扫描后状态栏应有完成信息。"""
    window._run_scan(test_data_dir)
    _wait_scan(qtbot, window)
    msg = window.status_bar.currentMessage()
    assert "扫描完成" in msg


def test_scan_table_has_correct_columns_filled(window, test_data_dir, qtbot):
    """扫描后表格各列应有数据。"""
    window._run_scan(test_data_dir)
    _wait_scan(qtbot, window)
    table = window.work_table
    row = 0
    # 序号 (col 0)
    assert table.item(row, 0) is not None
    seq_text = table.item(row, 0).text()
    assert seq_text.isdigit()
    # 工作状态 (col 1)
    assert table.item(row, 1).text() == "已扫描"
    # 标准编号 (col 2) 含标准代号
    assert len(table.item(row, 2).text()) > 0
