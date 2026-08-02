# tests/gui/test_coverage_table_helper_p1.py
"""TableHelperHandler P1 补测 — on_offline_view 5 分支 + enforce_min_column_width 3 条件路径。

覆盖方法:
  - on_offline_view (行 122-168): 离线查看标准信息，5 分支
  - enforce_min_column_width (行 260-273): 列宽强制最小值，3 条件路径
  - _save_column_widths (行 275-278): 列宽持久化到配置
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QMessageBox, QTableWidget

from pilotstd.models import ParsedStdInfo
from pilotstd.ui.core.handlers._table_helper import TableHelperHandler


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def handler(qtbot):
    """构造 TableHelperHandler，mock 所有外部依赖。

    qtbot 形参确保 QApplication 在 import TableHelperHandler 前已初始化。
    """
    config = MagicMock()
    mgr = MagicMock()
    h = TableHelperHandler(
        config=config,
        status_callback=MagicMock(),
        question_dlg=lambda *a, **kw: QMessageBox.StandardButton.Yes,
        mgr=mgr,
        run_scan_callback=MagicMock(),
        get_selected_path_callback=lambda: "/tmp",
        parent=None,
    )
    # 替换 engine 为 mock，隔离 TableHelperFlowEngine 的真实行为
    h._engine = MagicMock()
    return h


@pytest.fixture
def table(qtbot):
    """创建真实 QTableWidget 作为数据容器。"""
    t = QTableWidget()
    t.setColumnCount(10)
    qtbot.addWidget(t)
    return t


def _make_parsed(logical_code="GB", number=1, year=2020):
    """创建最小 ParsedStdInfo，含 logical_code / number / get_full_number()。"""
    return ParsedStdInfo(
        raw_filename=f"test_{number}.pdf",
        logical_code=logical_code,
        number=number,
        year=year,
    )


# ═══════════════════════════════════════════════════════════════
# on_offline_view — 5 分支
# ═══════════════════════════════════════════════════════════════

class TestOnOfflineView:
    """on_offline_view 5 分支全覆盖。

    分支路径:
      1. file_index 未初始化 → _status + return
      2. 无选中行 → return
      3. 选中行越界 (row >= len(parsed_results)) → return
      4. 本地索引无数据 → QMessageBox "未找到"
      5. 本地索引有数据 → QMessageBox 展示详情
    """

    def test_no_file_index_shows_status(self, handler, table):
        """file_index 未初始化 → _status 提示 + 提前返回，不弹 QMessageBox。"""
        handler._mgr.file_index = None
        table.setRowCount(1)
        table.selectRow(0)

        with patch.object(QMessageBox, "information") as mock_mb:
            handler.on_offline_view(table, [_make_parsed()])

        mock_mb.assert_not_called()
        handler._status.assert_called_once()

    def test_no_selected_row_silent_return(self, handler, table):
        """无选中行 → _status 和 QMessageBox 均不调用。"""
        handler._mgr.file_index = MagicMock()
        table.setRowCount(3)
        table.clearSelection()

        with patch.object(QMessageBox, "information") as mock_mb:
            handler.on_offline_view(table, [_make_parsed()])

        mock_mb.assert_not_called()
        handler._status.assert_not_called()

    def test_row_exceeds_parsed_results_silent_return(self, handler, table):
        """选中行号 >= parsed_results 长度 → 静默返回。"""
        handler._mgr.file_index = MagicMock()
        table.setRowCount(1)
        table.selectRow(0)

        with patch.object(QMessageBox, "information") as mock_mb:
            # parsed_results 为空列表，len=0，row=0 >= 0 → return
            handler.on_offline_view(table, [])

        mock_mb.assert_not_called()
        handler._status.assert_not_called()

    def test_empty_results_shows_not_found(self, handler, table):
        """get_file_index_full_info 返回空列表 → QMessageBox 提示"未找到"。"""
        handler._mgr.file_index = MagicMock()
        handler._mgr.get_file_index_full_info.return_value = []
        parsed = _make_parsed(logical_code="GB", number=1234, year=2024)
        table.setRowCount(1)
        table.selectRow(0)

        with patch.object(QMessageBox, "information") as mock_mb:
            handler.on_offline_view(table, [parsed])

        mock_mb.assert_called_once()
        msg_text = mock_mb.call_args[0][2]
        assert "未找到" in msg_text

    def test_results_found_shows_detail(self, handler, table):
        """get_file_index_full_info 有数据 → QMessageBox 展示多行详情。"""
        handler._mgr.file_index = MagicMock()
        handler._mgr.get_file_index_full_info.return_value = [
            {
                "file_path": "/tmp/GB 1234.pdf",
                "std_name": "测试标准名称",
                "found_name": "国家标准网",
                "effect_status": "现行",
                "is_adopted": True,
                "match_status": "精确匹配",
                "cached_at": "2024-07-01",
            }
        ]
        parsed = _make_parsed(logical_code="GB", number=1234, year=2024)
        table.setRowCount(1)
        table.selectRow(0)

        with patch.object(QMessageBox, "information") as mock_mb:
            handler.on_offline_view(table, [parsed])

        mock_mb.assert_called_once()
        detail = mock_mb.call_args[0][2]
        assert "GB" in detail
        assert "测试标准名称" in detail
        assert "国家标准网" in detail
        assert "现行" in detail
        assert "采标" in detail
        assert "精确匹配" in detail


# ═══════════════════════════════════════════════════════════════
# enforce_min_column_width + _save_column_widths — 3 条件路径
# ═══════════════════════════════════════════════════════════════

class TestEnforceMinColumnWidth:
    """enforce_min_column_width + _save_column_widths 3 条件路径。

    条件矩阵:
      1. col in col_specs AND new < min → 委托 engine + 保存列宽
      2. col not in col_specs → 跳过 engine，仍保存列宽
      3. col in col_specs AND new >= min → 跳过 engine，仍保存列宽
    """

    def test_delegates_to_engine_when_below_min(self, handler, table):
        """col in col_specs 且 new < min → 委托 engine.enforce_min_column_width。"""
        table.setColumnCount(3)
        table.setColumnWidth(0, 60)
        table.setColumnWidth(1, 100)
        table.setColumnWidth(2, 120)
        col_specs = {0: (200, 80)}  # col 0: (max=200, min=80)

        # mock engine 返回正确列宽，否则 resizeSection 收到 MagicMock 会设为零
        handler._engine.enforce_min_column_width.return_value = 80

        handler.enforce_min_column_width(
            table, col=0, _old=100, new=60, col_specs=col_specs
        )

        handler._engine.enforce_min_column_width.assert_called_once_with(60, 80)
        handler._config.set.assert_called_once_with(
            "appearance.column_widths", [80, 100, 120]
        )

    def test_skips_engine_when_col_not_in_specs(self, handler, table):
        """col 不在 col_specs 中 → 不委托 engine，但仍保存列宽。"""
        table.setColumnCount(2)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 200)
        col_specs = {0: (300, 100)}  # 仅约束 col 0

        handler.enforce_min_column_width(
            table, col=1, _old=200, new=180, col_specs=col_specs
        )

        handler._engine.enforce_min_column_width.assert_not_called()
        # col=1 不在 col_specs 中，resizeSection 未调用，列宽保持原值 200
        handler._config.set.assert_called_once_with(
            "appearance.column_widths", [150, 200]
        )

    def test_new_above_min_no_resize_still_saves(self, handler, table):
        """new >= min → 不触发 resize，但仍保存列宽。"""
        table.setColumnCount(1)
        table.setColumnWidth(0, 120)
        col_specs = {0: (300, 80)}  # min=80, new=120 >= 80

        handler.enforce_min_column_width(
            table, col=0, _old=100, new=120, col_specs=col_specs
        )

        handler._engine.enforce_min_column_width.assert_not_called()
        handler._config.set.assert_called_once_with(
            "appearance.column_widths", [120]
        )
