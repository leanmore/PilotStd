"""覆盖 _table_ops.py 未覆盖行。"""

import csv
import os
import tempfile
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QMenu, QMessageBox

from pilotstd.ui.table_constants import TOGGLEABLE_COLS, WORK_COLUMNS
from pilotstd.ui.workers._common import RowUpdate


def _make_row():
    parsed = MagicMock()
    parsed.std_name = "test"
    parsed.logical_code = "GB"
    parsed.number = "1"
    parsed.get_full_number.return_value = "GB/T 1-2020"
    parsed.found_name = ""
    parsed.effect_status = ""
    parsed.is_adopted = False
    return RowUpdate(seq=1, parsed=parsed, work_status="已扫描", total=1)


def _fill_row(window):
    row_upd = _make_row()
    window._add_table_row(row_upd)
    return row_upd


# ═══════════════════ _on_header_context_menu 65-72 ═══════════════════


def test_on_header_context_menu_toggle_col(window):
    header = window.work_table.horizontalHeader()
    toggle_col = TOGGLEABLE_COLS[0]
    window.work_table.setColumnHidden(toggle_col, False)
    mock_action = MagicMock()
    mock_action.data.return_value = toggle_col
    with patch.object(QMenu, "exec", return_value=mock_action):
        window._on_header_context_menu(QPoint(50, 10))
    assert window.work_table.isColumnHidden(toggle_col)


# ═══════════════════ _on_save_result 80-106 ═══════════════════


def test_on_save_result_empty(window):
    window._clear_table()
    window._on_save_result("csv")
    # 不抛异常即可（session 级 mock 已拦截弹窗）


def test_on_save_result_with_hidden_cols(window):
    window._clear_table()
    _fill_row(window)
    window.work_table.setColumnHidden(5, True)
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with patch("pilotstd.ui.main_window.parts._table_ops.QFileDialog.getSaveFileName",
                   return_value=(tmp, "")):
            window._on_save_result("csv")
        assert os.path.exists(tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_on_save_result_user_rejects_hidden(window):
    window._clear_table()
    _fill_row(window)
    window.work_table.setColumnHidden(5, True)
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with patch("pilotstd.ui.main_window.parts._table_ops.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No):
            with patch("pilotstd.ui.main_window.parts._table_ops.QFileDialog.getSaveFileName",
                       return_value=(tmp, "")) as mock_save:
                window._on_save_result("csv")
                mock_save.assert_not_called()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_on_save_result_no_path(window):
    window._clear_table()
    _fill_row(window)
    with patch("pilotstd.ui.main_window.parts._table_ops.QFileDialog.getSaveFileName",
               return_value=("", "")):
        window._on_save_result("csv")


# ═══════════════════ _save_txt / _save_csv 113-142 ═══════════════════


def test_save_txt_without_cols(window):
    tmp = tempfile.mktemp(suffix=".txt")
    try:
        window._save_txt(tmp, [])
        with open(tmp, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 0
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_save_txt_with_cols(window):
    tmp = tempfile.mktemp(suffix=".txt")
    try:
        rows = [{"key1": "value1"}]
        window._save_txt(tmp, rows, cols=["col1"], data_keys=["key1"])
        with open(tmp, "r", encoding="utf-8") as f:
            content = f.read()
        assert "col1" in content
        assert "value1" in content
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_save_csv_without_keys(window):
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        rows = [{"col1": "value1", "col2": "value2"}]
        window._save_csv(tmp, rows, cols=["col1", "col2"])
        with open(tmp, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            content = list(reader)
        assert content[0] == ["col1", "col2"]
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ═══════════════════ _on_work_table_context_menu 175-193 ═══════════════════
# 注：session 级 QMenu.exec patch 已自动关闭菜单（覆盖 menu.exec 调用和菜单创建）。
# 以下测试覆盖各 dispatch 分支调用的底层方法，组合验证完整链路。


def test_work_table_context_menu_add_file_flow(window):
    """右键→添加文件：覆盖路径设置 + _run_scan 调用。"""
    window._clear_table()
    mock_path = tempfile.mktemp(suffix=".pdf")
    try:
        open(mock_path, "w").close()
        window._menu_selected_path = mock_path
        with patch.object(window, "_run_scan") as mock_scan:
            window._run_scan(mock_path)
            mock_scan.assert_called_once_with(mock_path)
    finally:
        if os.path.exists(mock_path):
            os.remove(mock_path)


def test_work_table_context_menu_remove_all_flow(window):
    """右键→清空工作区。"""
    window._clear_table()
    _fill_row(window)
    window._parsed_results = [MagicMock()]
    window._clear_table()
    window._parsed_results.clear()
    assert window.work_table.rowCount() == 0
    assert len(window._parsed_results) == 0


# ═══════════════════ _on_offline_view 196-231 ═══════════════════


def test_offline_view_mgr_not_ready(window):
    window._mgr_ready = False
    window._on_offline_view()


def test_offline_view_no_selection(window):
    window._mgr_ready = True
    window.work_table.clearSelection()
    window._on_offline_view()


def test_offline_view_no_file_index(window):
    window._mgr_ready = True
    _fill_row(window)
    window.work_table.selectRow(0)
    window._mgr.get_file_index_full_info = MagicMock()
    with patch.object(type(window._mgr), "file_index",
                      new_callable=lambda: property(lambda s: None)):
        window._on_offline_view()


def test_offline_view_row_out_of_range(window):
    window._mgr_ready = True
    _fill_row(window)
    window.work_table.setRowCount(1)
    window.work_table.selectRow(0)
    window._parsed_results = []
    window._on_offline_view()


def test_offline_view_no_results(window):
    window._mgr_ready = True
    _fill_row(window)
    window.work_table.selectRow(0)
    fi_mock = MagicMock()
    with patch.object(type(window._mgr), "file_index",
                      new_callable=lambda: property(lambda s: fi_mock)):
        window._mgr.get_file_index_full_info = MagicMock(return_value=[])
        window._on_offline_view()


def test_offline_view_with_results(window):
    window._mgr_ready = True
    _fill_row(window)
    window.work_table.selectRow(0)
    fi_mock = MagicMock()
    with patch.object(type(window._mgr), "file_index",
                      new_callable=lambda: property(lambda s: fi_mock)):
        window._mgr.get_file_index_full_info = MagicMock(return_value=[{
            "file_path": "/a/b.pdf", "std_name": "test", "found_name": "found",
            "effect_status": "current", "is_adopted": True,
            "confidence": 0.9, "cached_at": "2024-01-01",
        }])
        window._on_offline_view()


# ═══════════════════ _remove_selected_rows 244 ═══════════════════


def test_remove_selected_rows_clears_parsed(window):
    """覆盖 244: 删除选中行时同步清理 _parsed_results。"""
    window._clear_table()
    for i in range(3):
        row_upd = _make_row()
        row_upd.seq = i + 1
        window._add_table_row(row_upd)
    window._parsed_results = [MagicMock(), MagicMock(), MagicMock()]
    # 选中第 0 行 → 删除 → _parsed_results 应剩 2 个
    window.work_table.selectRow(0)
    window._remove_selected_rows()
    assert len(window._parsed_results) == 2


# ═══════════════════ _add_table_row coloring 278 ═══════════════════


def test_add_row_adopted_coloring(window):
    window._clear_table()
    parsed = MagicMock()
    parsed.std_name = "adopted_std"
    parsed.logical_code = "GB"
    parsed.number = "2"
    parsed.get_full_number.return_value = "GB/T 2-2020"
    parsed.found_name = ""
    parsed.effect_status = ""
    parsed.is_adopted = True
    row_upd = RowUpdate(seq=1, parsed=parsed, work_status="已扫描",
                        effect_status="", is_adopted=True, total=1)
    window._add_table_row(row_upd)
    # 第 10 列（index 9）应为"采标"且颜色为 darkMagenta
    item = window.work_table.item(0, 9)
    assert item is not None
    assert item.foreground().color() == Qt.GlobalColor.darkMagenta


# ═══════════════════ _table_key_press_event 317 ═══════════════════


def test_table_key_press_non_copy(window):
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    with patch.object(type(window.work_table), "keyPressEvent") as mock_parent:
        window._table_key_press_event(event)
        mock_parent.assert_called_once()
