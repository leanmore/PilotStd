# pilotstd/ui/core/handlers/_table_helper.py
"""TableHelperHandler — 工作表右键菜单、行操作、列宽管理，替代 TableHelperMixin。"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ....i18n import _
from ...table_constants import WORK_COLUMNS
from ...workers import RowUpdate
from .table_helper_flow_engine import TableHelperFlowEngine

logger = logging.getLogger(__name__)


class TableHelperHandler:
    """工作表右键菜单、行操作、列宽管理。

    通过依赖注入替代多重继承，work_table/parsed_results/col_specs 作为方法参数传入，
    Handler 不持有控件引用，不发射 Qt 信号，通过 _status 回调与上层通信。
    """

    def __init__(
        self,
        config: Any,  # ConfigManager
        status_callback: Callable[[str], None],
        question_dlg: Callable[[str, str], QMessageBox.StandardButton],
        mgr: Any,  # StandardManager（离线视图需要）
        run_scan_callback: Callable[[str], None],  # 右键菜单"添加文件/文件夹"触发扫描
        get_selected_path_callback: Callable[[], str],  # 右键菜单"添加文件夹"的默认路径
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._status = status_callback
        self._question = question_dlg
        self._mgr = mgr
        self._run_scan = run_scan_callback
        self._get_selected_path = get_selected_path_callback
        self._parent = parent
        self._engine = TableHelperFlowEngine()

    # ── 右键菜单 ─────────────────────────────────────────

    def on_work_table_context_menu(
        self,
        work_table: QTableWidget,
        parsed_results: list[Any],
        pos: Any,
    ) -> None:
        """工作表右键菜单：📋复制 | 🔍离线查看 | 📄增加文件 | 📁增加文件夹 | 🗑移除所选 | 🧹移除全部。"""
        menu = QMenu(work_table)

        copy_action = menu.addAction(f"📋 {_('copy')}")
        copy_action.setToolTip(_("复制选中单元格内容至剪贴板"))

        menu.addSeparator()

        offline_action = menu.addAction(f"🔍 {_('offline_view')}")
        offline_action.setToolTip(_("从本地索引和缓存查看标准完整信息（无需联网）"))
        if not work_table.selectedItems():
            offline_action.setEnabled(False)

        add_file = menu.addAction(f"📄 {_('add_file')}")
        add_file.setToolTip(_("选择一个标准文件加入工作区"))
        add_folder = menu.addAction(f"📁 {_('add_folder')}")
        add_folder.setToolTip(_("选择一个文件夹加入工作区"))

        menu.addSeparator()

        remove_selected = menu.addAction(f"🗑 {_('remove_selected')}")
        remove_selected.setToolTip(_("从工作区表格中移除选中的行（不删除物理文件）"))
        remove_all = menu.addAction(f"🧹 {_('remove_all')}")
        remove_all.setToolTip(_("清空工作区表格（不删除物理文件）"))

        if work_table.rowCount() == 0:
            remove_selected.setEnabled(False)
            remove_all.setEnabled(False)
        if not work_table.selectedItems():
            remove_selected.setEnabled(False)

        chosen = menu.exec(work_table.viewport().mapToGlobal(pos))

        if chosen == copy_action:
            self.copy_selected_cells(work_table)
        elif chosen == offline_action:
            self.on_offline_view(work_table, parsed_results)
        elif chosen == add_file:
            path, _filter = QFileDialog.getOpenFileName(
                work_table,
                _("dialog_select_file"),
                "",
                "标准文件 (*.pdf *.doc *.docx *.txt);;所有文件 (*)",
            )
            if path:
                self._run_scan(path)
        elif chosen == add_folder:
            start = self._get_selected_path()
            path = QFileDialog.getExistingDirectory(work_table, _("dialog_select_folder"), start)
            if path:
                self._run_scan(path)
        elif chosen == remove_selected:
            self.remove_selected_rows(work_table, parsed_results)
        elif chosen == remove_all:
            self.clear_table(work_table)
            parsed_results.clear()
            self._status(_("status_workspace_cleared"))

    # ── 离线查看 ─────────────────────────────────────────

    def on_offline_view(
        self,
        work_table: QTableWidget,
        parsed_results: list[Any],
    ) -> None:
        """离线查看：从本地索引和缓存联合查询标准信息。"""
        if not self._mgr.file_index:
            self._status(_("status_file_index_not_init"))
            return

        rows = {r.row() for r in work_table.selectedIndexes()}
        if not rows:
            return

        row = min(rows)
        if row >= len(parsed_results):
            return

        parsed = parsed_results[row]
        results = self._mgr.get_file_index_full_info(parsed.logical_code, parsed.number)

        if not results:
            QMessageBox.information(
                work_table,
                _("offline_view"),
                _("本地索引中未找到 {} 的相关信息").format(parsed.get_full_number()),
            )
            return

        lines = [f"=== {parsed.get_full_number()} ===\n"]
        for r in results:
            lines.append(_("文件: {}").format(r["file_path"]))
            if r["std_name"]:
                lines.append(_("名称: {}").format(r["std_name"]))
            if r["found_name"]:
                lines.append(_("网站名称: {}").format(r["found_name"]))
            if r["effect_status"]:
                lines.append(_("状态: {}").format(r["effect_status"]))
            if r["is_adopted"]:
                lines.append(_("采标: 是"))
            if r["match_status"]:
                lines.append(_("置信度: {}").format(r["match_status"]))
            if r["cached_at"]:
                lines.append(_("缓存时间: {}").format(r["cached_at"]))
            lines.append("")

        QMessageBox.information(work_table, _("offline_view"), "\n".join(lines))

    # ── 行操作 ───────────────────────────────────────────

    def remove_selected_rows(
        self,
        work_table: QTableWidget,
        parsed_results: list[Any],
    ) -> None:
        """移除表格中选中的行，同步更新 parsed_results。"""
        rows = set()
        for item in work_table.selectedItems():
            rows.add(item.row())
        if not rows:
            return
        removed = 0
        for r in sorted(rows, reverse=True):
            work_table.removeRow(r)
            if r < len(parsed_results):
                del parsed_results[r]
            removed += 1
        self._status(f"已移除 {removed} 行")

    def add_table_row(self, work_table: QTableWidget, update: RowUpdate) -> None:
        """向表格末尾插入一行。"""
        # [TRACE] 指令A-4: 输出最终传入add_table_row的parsed对象
        logger.debug(
            "[TRACE-A] add_table_row: 行号=%d 标准号=%r 标准名称=%r "
            "工作状态=%r 生效状态=%r 是否采标=%s "
            "代号=%s 序号=%s 年份=%s 部分=%s",
            update.seq,
            update.parsed.get_full_number(),
            update.std_name_override or update.parsed.std_name,
            update.work_status,
            update.effect_status,
            update.is_adopted,
            getattr(update.parsed, "logical_code", ""),
            getattr(update.parsed, "number", 0),
            getattr(update.parsed, "year", 0),
            getattr(update.parsed, "part", None),
        )
        row = work_table.rowCount()
        work_table.insertRow(row)
        width = max(2, len(str(update.total))) if update.total else max(2, len(str(update.seq)))
        std_num = update.parsed.get_full_number()
        items = [
            QTableWidgetItem(f"{update.seq:0{width}d}"),
            QTableWidgetItem(update.work_status),
            QTableWidgetItem(std_num),
            QTableWidgetItem(update.std_name_override or update.parsed.std_name),
            QTableWidgetItem(update.effect_status),
            QTableWidgetItem(getattr(update.parsed, "found_replaces", "")),
            QTableWidgetItem(update.publish_date),
            QTableWidgetItem(update.implement_date),
            QTableWidgetItem(update.responsible_dept),
            QTableWidgetItem("采标" if update.is_adopted else ""),
        ]
        for c, item in enumerate(items):
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if c == 9 and update.is_adopted and item.text() == "采标":
                item.setForeground(Qt.GlobalColor.darkMagenta)
            work_table.setItem(row, c, item)

    def clear_table(self, work_table: QTableWidget) -> None:
        """清空表格所有行。"""
        work_table.setRowCount(0)

    def find_row_by_seq(self, work_table: QTableWidget, seq: int) -> int:
        """按序号查找行号，未找到返回 -1。"""
        for r in range(work_table.rowCount()):
            item = work_table.item(r, 0)
            if item and item.text() and int(item.text()) == seq:
                return r
        return -1

    def table_to_list(self, work_table: QTableWidget) -> list[Any]:
        """将表格所有行导出为字典列表。"""
        rows = []
        for r in range(work_table.rowCount()):
            row_data = {}
            for c in range(work_table.columnCount()):
                item = work_table.item(r, c)
                row_data[WORK_COLUMNS[c]] = item.text() if item else ""
            rows.append(row_data)
        return rows

    # ── 列宽管理 ─────────────────────────────────────────

    def enforce_min_column_width(
        self,
        work_table: QTableWidget,
        col: int,
        _old: int,
        new: int,
        col_specs: dict[int, tuple[int, int]],
    ) -> None:
        """强制最小列宽：当新宽度小于最小值时恢复。"""
        if col in col_specs:
            mn = col_specs[col][1]
            if new < mn:
                work_table.horizontalHeader().resizeSection(
                    col, self._engine.enforce_min_column_width(new, mn)
                )
        self._save_column_widths(work_table)

    def _save_column_widths(self, work_table: QTableWidget) -> None:
        """将当前列宽保存到配置。"""
        widths = [work_table.columnWidth(c) for c in range(work_table.columnCount())]
        self._config.set("appearance.column_widths", widths)

    # ── 剪贴板 ───────────────────────────────────────────

    def copy_selected_cells(self, work_table: QTableWidget) -> None:
        """将选中单元格内容以制表符分隔复制到剪贴板。"""
        selected = work_table.selectedIndexes()
        if not selected:
            return
        rows_set = sorted(set(i.row() for i in selected))
        cols_set = sorted(set(i.column() for i in selected))
        lines = []
        for r in rows_set:
            cells = []
            for c in cols_set:
                item = work_table.item(r, c)
                cells.append(item.text() if item else "")
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))
