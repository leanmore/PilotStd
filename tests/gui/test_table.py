# tests/gui/test_table.py
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.ui.table_constants import WORK_COLUMNS


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


def test_seq_dynamic_width(window):
    """序号宽度随总数动态增长：1-9→2位，10-99→2位，100+→3位以上。"""
    from pilotstd.organizer.industry_lookup import build_code_mapping
    from pilotstd.scan.parser import StandardParser
    from pilotstd.ui.workers._common import RowUpdate

    parser = StandardParser(build_code_mapping())
    window._clear_table()

    # 扫描 150 个文件，序号应从 01 增长到 150，宽度从 2 位变成 3 位
    for i in range(1, 151):
        parsed = parser.parse("GB/T 1-2000.pdf")
        parsed.source_path = f"test_{i}.pdf"
        window._add_table_row(RowUpdate(seq=i, parsed=parsed, work_status="已扫描", total=150))

    table = window.work_table
    assert table.rowCount() == 150
    # 第 1 行序号应为 "001"（宽度=3，因为 total=150）
    assert table.item(0, 0).text() == "001"
    # 第 100 行序号应为 "100"
    assert table.item(99, 0).text() == "100"
    # 第 150 行序号应为 "150"
    assert table.item(149, 0).text() == "150"
