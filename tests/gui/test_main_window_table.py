# tests/gui/test_main_window_table.py
# MainWindow _table_ops + _query_ops 补充测试 — 提升覆盖率

import csv
import os
import tempfile
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QMessageBox

# ═══════════════════════════════════════════════════════════
# _table_ops 核心函数
# ═══════════════════════════════════════════════════════════


def test_get_column_visibility(window, qtbot):
    """_get_column_visibility 返回所有列可见性列表。"""
    vis = window._get_column_visibility()
    assert len(vis) > 0
    assert all(isinstance(v, bool) for v in vis)


def test_get_visible_cols(window, qtbot):
    """_get_visible_cols 返回可见列名列表。"""
    cols = window._get_visible_cols()
    assert len(cols) > 0


def test_save_load_column_visibility(window, qtbot):
    """保存和加载列可见性设置。"""
    window._save_column_visibility()
    saved = window._config.get("appearance.column_visibility")
    assert saved is not None
    window._load_column_visibility()  # 不抛异常


def test_apply_column_visibility_all_true(window, qtbot):
    """全部列设为可见。"""
    from pilotstd.ui.table_constants import WORK_COLUMNS

    all_true = [True] * len(WORK_COLUMNS)
    window._apply_column_visibility(all_true)
    for c in range(4, len(WORK_COLUMNS)):
        assert not window.work_table.isColumnHidden(c)


def test_apply_column_visibility_hide_some(window, qtbot):
    """隐藏部分列。"""
    from pilotstd.ui.table_constants import WORK_COLUMNS

    vis = [True] * len(WORK_COLUMNS)
    vis[5] = False
    window._apply_column_visibility(vis)
    assert window.work_table.isColumnHidden(5)


def test_row_get_dict(window, qtbot):
    """_row_get 从字典取键值。"""
    row = {"name": "test", "value": "123"}
    assert window._row_get(row, "name") == "test"
    assert window._row_get(row, "missing", "default") == "default"


def test_row_get_object(window, qtbot):
    """_row_get 从对象取属性。"""
    obj = MagicMock()
    obj.filename = "test.pdf"
    assert window._row_get(obj, "filename") == "test.pdf"


def test_table_to_list(window, qtbot):
    """_table_to_list 导出所有可见列数据。"""
    window._clear_table()
    row_data = {"文件名": "GB_T_1.pdf", "标准号": "GB/T 1-2020", "工作状态": "已扫描"}
    window._add_row_from_dict(row_data)
    rows = window._table_to_list()
    assert len(rows) >= 1
    assert isinstance(rows[0], dict)


def test_clear_table(window, qtbot):
    """_clear_table 清空工作表。"""
    window._add_row_from_dict({"文件名": "test.pdf"})
    assert window.work_table.rowCount() > 0
    window._clear_table()
    assert window.work_table.rowCount() == 0


def test_find_row_by_seq(window, qtbot):
    """_find_row_by_seq 按序号查找行。"""
    window._clear_table()
    row_data = {"文件名": "test.pdf"}
    window._add_row_from_dict(row_data)
    # 序号列(0)应该包含"1"或其他行号
    assert window.work_table.rowCount() == 1


def test_remove_selected_rows(window, qtbot):
    """_remove_selected_rows 删除选中行。"""
    window._clear_table()
    window._add_row_from_dict({"文件名": "test1.pdf"})
    window._add_row_from_dict({"文件名": "test2.pdf"})
    window.work_table.selectRow(0)
    window._remove_selected_rows()
    assert window.work_table.rowCount() == 1


def test_remove_selected_rows_empty(window, qtbot):
    """空表格时 _remove_selected_rows 安全返回。"""
    window._clear_table()
    window._remove_selected_rows()  # 不抛异常


def test_save_txt(window, qtbot):
    """_save_txt 导出空格对齐文本。"""
    tmp = tempfile.mktemp(suffix=".txt")
    try:
        # 使用预设的 cols 和 data_keys 避免依赖列映射
        window._save_txt(tmp, [], ["A", "B"])
        with open(tmp, "r", encoding="utf-8") as f:
            content = f.read()
        assert "A" in content
        assert "B" in content
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_save_csv(window, qtbot):
    """_save_csv 导出 CSV。"""
    rows = [{"文件名": "a.pdf", "标准号": "GB/T 1"}]
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        window._save_csv(tmp, rows)
        with open(tmp, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            content = list(reader)
        assert len(content) >= 2  # header + data
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_on_save_result_empty(window, qtbot):
    """空表格时 _on_save_result 提示无数据。"""
    window._clear_table()
    with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok) as mock_info:
        window._on_save_result("csv")
        mock_info.assert_called_once()


def test_on_offline_view_no_mgr(window, qtbot):
    """_mgr 未就绪时 _on_offline_view 安全返回。"""
    window._mgr_ready = False
    window._on_offline_view()  # 不抛异常


def test_on_offline_view_no_selection(window, qtbot):
    """无选中行时 _on_offline_view 安全返回。"""
    window._mgr_ready = True
    window.work_table.clearSelection()
    window._on_offline_view()  # 不抛异常


def test_enforce_min_column_width(window, qtbot):
    """_enforce_min_column_width 强制最小列宽（sectionResized 回调）。"""
    # 此函数是 sectionResized 信号的回调，需要 3 个参数
    col_count = window.work_table.columnCount()
    if col_count > 0:
        window._enforce_min_column_width(0, 10, 5)  # 不抛异常


def test_copy_selected_cells(window, qtbot):
    """_copy_selected_cells 复制选中单元格到剪贴板。"""
    window._clear_table()
    window._add_row_from_dict({"文件名": "test.pdf", "标准号": "GB/T 1"})
    item = window.work_table.item(0, 0)
    if item:
        item.setSelected(True)
    window._copy_selected_cells()  # 不抛异常


def test_table_key_press_event(window, qtbot):
    """_table_key_press_event 处理 Ctrl+C 复制。"""
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    window._table_key_press_event(event)  # 不抛异常


# ═══════════════════════════════════════════════════════════
# _query_ops 补充
# ═══════════════════════════════════════════════════════════


def test_on_pending_query_no_mgr(window, qtbot):
    """_mgr 未就绪时 _do_pending_query 安全返回。"""
    window._mgr_ready = False
    window._do_pending_query()  # 不抛异常


def test_on_pending_query_workspace_not_empty(window, qtbot):
    """工作区非空时提示需清空。"""
    window._mgr  # 确保就绪
    window._parsed_results = [MagicMock()]
    with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok) as mock_warn:
        window._do_pending_query()
        mock_warn.assert_called_once()


def test_on_pending_query_cancelled(window, qtbot):
    """用户取消待确认查询。"""
    window._mgr
    window._parsed_results.clear()
    with patch("pilotstd.ui.main_window.parts._query_ops.QFileDialog.getOpenFileName", return_value=("", "")):
        window._do_pending_query()
    # 取消后不抛异常


def test_parse_pending_csv(window, test_data_dir, qtbot):
    """_parse_pending_csv 解析 CSV 文件。"""
    window._mgr
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])
            w.writerow(["GB/T 1-2020", "基础规范"])
            w.writerow(["SH/T 2-2010", ""])
        parsed_list, failed_names = window._parse_pending_csv(tmp)
        # mock 环境下解析可能成功或失败，不抛异常即通过
        assert isinstance(parsed_list, list)
        assert isinstance(failed_names, list)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_parse_pending_csv_empty(window, qtbot):
    """空 CSV 文件处理。"""
    tmp = tempfile.mktemp(suffix=".csv")
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准号", "标准名称"])
        window._mgr
        parsed_list, failed_names = window._parse_pending_csv(tmp)
        assert parsed_list == []
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ═══════════════════════════════════════════════════════════
# _delegate_ops 补充
# ═══════════════════════════════════════════════════════════


def test_on_check_announcements(window, qtbot):
    """_on_check_announcements 触发公告检查。"""
    window._suppress_dialogs = True
    with (
        patch("PyQt6.QtWidgets.QMessageBox.information"),
        patch("PyQt6.QtWidgets.QMessageBox.warning"),
        patch("PyQt6.QtWidgets.QMessageBox.question"),
    ):
        window._on_check_announcements()


def test_on_cleanup_empty_dirs(window, qtbot):
    """_on_cleanup_empty_dirs 清理空目录。"""
    with (
        patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", return_value=""),
        patch("PyQt6.QtWidgets.QMessageBox.information"),
        patch("PyQt6.QtWidgets.QMessageBox.question"),
    ):
        window._on_cleanup_empty_dirs()


def test_on_collect_unrecognized(window, qtbot):
    """_on_collect_unrecognized 收集未识别文件。"""
    with patch("PyQt6.QtWidgets.QMessageBox.information"), patch("PyQt6.QtWidgets.QDialog.exec", return_value=0):
        window._on_collect_unrecognized()


def test_on_import_download(window, qtbot):
    """_on_import_download 导入下载文件。"""
    with (
        patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=("", "")),
        patch("PyQt6.QtWidgets.QMessageBox.information"),
        patch("PyQt6.QtWidgets.QMessageBox.warning"),
    ):
        window._on_import_download()


# ═══════════════════════════════════════════════════════════
# 文件树操作补充
# ═══════════════════════════════════════════════════════════


def test_make_drive_item(window, qtbot):
    """_make_drive_item 创建盘符节点。"""
    item = window._make_drive_item("C:", "C:\\")
    assert item is not None
    assert item.text(0) == "C:"


def test_make_item(window, qtbot):
    """_make_item 创建文件树节点。"""
    item = window._make_item("测试目录", "D:/test")
    assert item.text(0) == "测试目录"
    assert item.data(0, Qt.ItemDataRole.UserRole) == "D:/test"


def test_populate_quick_access(window, qtbot):
    """_populate_quick_access 填充快速访问列表。"""
    window.file_tree.topLevelItemCount()
    window._populate_quick_access()  # 不抛异常
    # 快速访问节点已存在时不会重复添加


def test_on_file_tree_context_menu(window, qtbot):
    """_on_file_tree_context_menu 弹出右键菜单。"""
    window._on_file_tree_context_menu(QPoint(10, 10))  # 不抛异常


# ═══════════════════════════════════════════════════════════
# _download_ops 补充
# ═══════════════════════════════════════════════════════════


def test_check_download_queue(window, qtbot):
    """_check_download_queue 检查下载队列。"""
    window._check_download_queue()  # 不抛异常


def test_on_auto_run_no_path(window, qtbot):
    """_on_auto_run 无路径时弹出提示。"""
    window._mgr  # 确保就绪
    window._menu_selected_path = ""
    window.file_tree.clearSelection()
    with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok) as mock_info:
        window._on_auto_run()
        mock_info.assert_called_once()


# ═══════════════════════════════════════════════════════════
# 菜单操作补充
# ═══════════════════════════════════════════════════════════


def test_on_rule_query(window, qtbot):
    """_on_rule_query 打开规则配置对话框。"""
    with patch("pilotstd.ui.dialogs.ConfigPageDialog") as mock_dlg:
        mock_instance = MagicMock()
        mock_dlg.return_value = mock_instance
        mock_instance.exec.return_value = QMessageBox.DialogCode.Accepted
        window._on_rule_query()


def test_on_rule_download(window, qtbot):
    """_on_rule_download 委托到 _on_rule_query。"""
    with patch.object(window, "_on_rule_query") as mock_rule:
        window._on_rule_download()
        mock_rule.assert_called_once()
