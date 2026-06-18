import os
import shutil
import sys
import tempfile

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


def test_query_requires_scan_first(window, qtbot):
    """未导入时点击查询应弹出提示。"""
    window._parsed_results.clear()
    window._clear_table()
    window._on_query()
    qtbot.wait(200)
    assert len(window._parsed_results) == 0


def test_query_mock_populates_status(window, test_data_dir, qtbot):
    """mock 模式下扫描→查询后状态列应有值。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        qtbot.wait(300)
        window._on_query()
        qtbot.wait(1000)
        table = window.work_table
        assert table.rowCount() > 0
        for row in range(table.rowCount()):
            status_item = table.item(row, 1)
            if status_item:
                text = status_item.text()
                assert "查询" in text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_query_mock_changes_effect_status(window, test_data_dir, qtbot):
    """mock 查询后生效状态列应有值。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        qtbot.wait(300)
        window._on_query()
        qtbot.wait(1000)
        table = window.work_table
        has_status = False
        for row in range(table.rowCount()):
            item = table.item(row, 4)
            if item and item.text():
                has_status = True
                break
        assert has_status
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_query_progress_bar_shows(window, test_data_dir, qtbot):
    """查询过程中进度条应可见。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        qtbot.wait(300)
        window._on_query()
        qtbot.wait(200)
        assert window.progress_bar.isVisible()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
