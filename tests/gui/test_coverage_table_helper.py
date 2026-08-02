"""TableHelperHandler 纯逻辑方法补测试 — P0-B 首批 4 个方法"""

import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QTableWidget

from pilotstd.models import ParsedStdInfo
from pilotstd.ui.workers import RowUpdate


@pytest.fixture
def handler(qtbot):
    """TableHelperHandler 最小构造 fixture"""
    from pilotstd.ui.core.handlers._table_helper import TableHelperHandler

    config = MagicMock()
    mgr = MagicMock()

    return TableHelperHandler(
        config=config,
        status_callback=lambda x: None,
        question_dlg=lambda *a, **kw: True,
        mgr=mgr,
        run_scan_callback=lambda x: None,
        get_selected_path_callback=lambda: "/tmp",
        parent=None,
    )


def _make_parsed(seq=1, logical_code="GB", number=1, year=2020):
    """创建最小 ParsedStdInfo 用于 RowUpdate 构造"""
    return ParsedStdInfo(
        raw_filename=f"test_{seq}.pdf",
        logical_code=logical_code,
        number=number,
        year=year,
    )


def _make_table(qtbot, columns=10):
    """创建真实 QTableWidget 作为数据容器"""
    t = QTableWidget()
    t.setColumnCount(columns)
    qtbot.addWidget(t)
    return t


class TestAddTableRow:
    """add_table_row: 10 列数据正确填充"""

    def test_fills_all_columns(self, handler, qtbot):
        table = _make_table(qtbot)
        parsed = _make_parsed(seq=1, logical_code="GB", number=1234, year=2024)
        update = RowUpdate(
            seq=1,
            parsed=parsed,
            work_status="已扫描",
            effect_status="现行",
            implement_date="2024-07-01",
            std_name_override="测试标准",
            responsible_dept="标准委",
            publish_date="2024-01-01",
            is_adopted=False,
            total=5,
        )
        handler.add_table_row(table, update)

        assert table.rowCount() == 1
        # 序号列 — total=5 时 width=2，补零为 "01"
        assert table.item(0, 0).text() == "01"
        # 工作状态列
        assert table.item(0, 1).text() == "已扫描"
        # 标准号列
        assert "GB" in table.item(0, 2).text()
        # 名称列（override 优先）
        assert table.item(0, 3).text() == "测试标准"
        # 生效状态
        assert table.item(0, 4).text() == "现行"

    def test_adopted_flag_sets_purple_foreground(self, handler, qtbot):
        parsed = _make_parsed()
        update = RowUpdate(seq=1, parsed=parsed, work_status="已查询", is_adopted=True)
        table = _make_table(qtbot)
        handler.add_table_row(table, update)

        item = table.item(0, 9)
        assert item.text() == "采标"


class TestRemoveSelectedRows:
    """remove_selected_rows: 表格 + parsed_results 同步删除"""

    def test_removes_row_and_syncs_list(self, handler, qtbot):
        table = _make_table(qtbot)
        parsed_list = [_make_parsed(number=1), _make_parsed(number=2), _make_parsed(number=3)]

        for i, p in enumerate(parsed_list):
            handler.add_table_row(table, RowUpdate(seq=i + 1, parsed=p, work_status="已扫描"))

        table.selectRow(1)

        handler.remove_selected_rows(table, parsed_list)

        assert table.rowCount() == 2
        assert len(parsed_list) == 2
        assert parsed_list[0].number == 1
        assert parsed_list[1].number == 3

    def test_no_selection_does_nothing(self, handler, qtbot):
        table = _make_table(qtbot)
        parsed_list = [_make_parsed(1)]
        handler.add_table_row(table, RowUpdate(seq=1, parsed=parsed_list[0], work_status="已扫描"))

        handler.remove_selected_rows(table, parsed_list)

        assert table.rowCount() == 1
        assert len(parsed_list) == 1


class TestTableToList:
    """table_to_list: 导出为 list[dict]，列数匹配"""

    def test_exports_correct_structure(self, handler, qtbot):
        table = _make_table(qtbot)
        for i in range(2):
            parsed = _make_parsed(seq=i + 1)
            handler.add_table_row(table, RowUpdate(seq=i + 1, parsed=parsed, work_status="已扫描"))

        result = handler.table_to_list(table)

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], dict)

    def test_empty_table_returns_empty_list(self, handler, qtbot):
        table = _make_table(qtbot)
        result = handler.table_to_list(table)
        assert result == []


class TestFindRowBySeq:
    """find_row_by_seq: 存在返回行号，不存在返回 -1"""

    def test_found_returns_index(self, handler, qtbot):
        table = _make_table(qtbot)
        for i in range(3):
            parsed = _make_parsed(seq=42 + i)
            handler.add_table_row(table, RowUpdate(seq=42 + i, parsed=parsed, work_status="已扫描"))

        assert handler.find_row_by_seq(table, 42) == 0
        assert handler.find_row_by_seq(table, 44) == 2

    def test_not_found_returns_minus_one(self, handler, qtbot):
        table = _make_table(qtbot)
        parsed = _make_parsed(seq=1)
        handler.add_table_row(table, RowUpdate(seq=1, parsed=parsed, work_status="已扫描"))

        assert handler.find_row_by_seq(table, 999) == -1

    def test_empty_table_returns_minus_one(self, handler, qtbot):
        table = _make_table(qtbot)
        assert handler.find_row_by_seq(table, 1) == -1
