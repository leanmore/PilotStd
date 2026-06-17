# tests/gui/test_table.py
import os
import sys
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.ui.table_mixin import WORK_COLUMNS


def test_table_has_all_columns(window):
    """表格应有全部 10 列且列头正确。"""
    table = window.work_table
    assert table.columnCount() == 10
    for i, name in enumerate(WORK_COLUMNS):
        item = table.horizontalHeaderItem(i)
        assert item is not None
        assert item.text() == name


def test_table_default_column_widths(window):
    """默认列宽匹配 _col_specs 定义，Stretch 列只校验最小值。"""
    from PyQt6.QtWidgets import QHeaderView
    table = window.work_table
    header = table.horizontalHeader()
    specs = window._col_specs
    for col, (w, mn) in specs.items():
        mode = header.sectionResizeMode(col)
        if mode == QHeaderView.ResizeMode.Stretch:
            # Stretch 列宽由布局决定，校验 >= 全局最小宽度即可
            assert table.columnWidth(col) >= header.minimumSectionSize()
        else:
            assert table.columnWidth(col) == w


def test_table_sorting_enabled(window):
    """表格排序功能启用。"""
    assert window.work_table.isSortingEnabled()


def test_table_no_edit_triggers(window):
    """表格单元格不可编辑。"""
    from PyQt6.QtWidgets import QTableWidget
    assert window.work_table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers


def test_table_selection_is_item_based(window):
    """表格选择行为是按单元格选择（支持 Ctrl+C 复制）。"""
    from PyQt6.QtWidgets import QTableWidget
    assert window.work_table.selectionBehavior() == QTableWidget.SelectionBehavior.SelectItems
