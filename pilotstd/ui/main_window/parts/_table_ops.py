"""表格管理与交互操作 — 列可见性控制、右键菜单、增删行、复制粘贴。

数据导出函数已提取到 _table_io.py，此处重导出以保持向后兼容。
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
)

from ....i18n import _
from ...table_constants import TOGGLEABLE_COLS, WORK_COLUMN_KEYS, WORK_COLUMNS
from ...workers import RowUpdate

# 重导出数据/函数，保持类体导入链路不中断
from ._table_io import (  # noqa: F401 — 由 MainWindow 类体导入消费
    _get_visible_cols,
    _on_save_result,
    _row_get,
    _save_csv,
    _save_txt,
    _table_to_list,
)

logger = logging.getLogger("pilotstd.ui")


# ── 列可见性管理 ──


def _get_column_visibility(self) -> list[bool]:
    """获取当前各列的可见状态（True=可见）。"""
    return [not self.work_table.isColumnHidden(c) for c in range(len(WORK_COLUMNS))]


def _apply_column_visibility(self, visible: list[bool]) -> None:
    """应用列可见性设置，前 4 列（序号/状态/标准号/名称）始终可见。"""
    header = self.work_table.horizontalHeader()
    for c in range(len(WORK_COLUMNS)):
        if c < 4:
            self.work_table.setColumnHidden(c, False)
        elif c < len(visible):
            hidden = not visible[c]
            self.work_table.setColumnHidden(c, hidden)
            if hidden:
                header.resizeSection(c, 0)
            elif hasattr(self, "_col_specs") and c in self._col_specs:
                header.resizeSection(c, self._col_specs[c][0])


def _save_column_visibility(self) -> None:
    """保存当前列可见性到配置。"""
    self._config.set("appearance.column_visibility", self._get_column_visibility())


def _load_column_visibility(self) -> None:
    """从配置加载列可见性并应用。"""
    default = [True] * len(WORK_COLUMNS)
    visible = self._config.get("appearance.column_visibility", default) or default
    self._apply_column_visibility(visible)


# ── 表头右键菜单 ──


def _on_header_context_menu(self, pos: Any) -> None:
    """表头右键菜单：显示/隐藏可切换列。"""
    header = self.work_table.horizontalHeader()
    menu = QMenu(self.work_table)
    for c in TOGGLEABLE_COLS:
        action = menu.addAction(_(WORK_COLUMN_KEYS[c]))
        action.setCheckable(True)
        action.setChecked(not self.work_table.isColumnHidden(c))
        action.setData(c)
    chosen = menu.exec(header.viewport().mapToGlobal(pos))
    menu.deleteLater()
    if chosen:
        c = chosen.data()
        hidden = not self.work_table.isColumnHidden(c)
        self.work_table.setColumnHidden(c, hidden)
        if hidden:
            header.resizeSection(c, 0)
        elif hasattr(self, "_col_specs") and c in self._col_specs:
            header.resizeSection(c, self._col_specs[c][0])
        self._save_column_visibility()


# ── 工作区右键菜单 ──


def _on_work_table_context_menu(self, pos: Any) -> None:
    """构建工作区表格右键菜单：复制、离线查看、添加文件/文件夹、删除行。"""
    menu = QMenu(self)
    copy_action = menu.addAction(f"\U0001f4cb {_('copy')}")
    copy_action.setToolTip("复制选中单元格内容至剪贴板")
    copy_action.triggered.connect(self._copy_selected_cells)
    menu.addSeparator()
    offline_action = menu.addAction(f"\U0001f50d {_('offline_view')}")
    offline_action.setToolTip("从本地索引和缓存查看标准完整信息（无需联网）")
    offline_action.triggered.connect(self._on_offline_view)
    if not self.work_table.selectedItems():
        offline_action.setEnabled(False)
    add_file = menu.addAction(f"\U0001f4c4 {_('add_file')}")
    add_file.setToolTip("选择一个标准文件加入工作区")
    add_folder = menu.addAction(f"\U0001f4c1 {_('add_folder')}")
    add_folder.setToolTip("选择一个文件夹加入工作区")
    menu.addSeparator()
    remove_selected = menu.addAction(f"\U0001f5d1 {_('remove_selected')}")
    remove_selected.setToolTip("从工作区表格中移除选中的行（不删除物理文件）")
    remove_all = menu.addAction(f"\U0001f9f9 {_('remove_all')}")
    remove_all.setToolTip("清空工作区表格（不删除物理文件）")
    if self.work_table.rowCount() == 0:
        remove_selected.setEnabled(False)
        remove_all.setEnabled(False)
    if not self.work_table.selectedItems():
        remove_selected.setEnabled(False)
    chosen = menu.exec(self.work_table.viewport().mapToGlobal(pos))
    if chosen == add_file:
        path, _filter = QFileDialog.getOpenFileName(
            self, _("dialog_select_file"), "", "标准文件 (*.pdf *.doc *.docx *.txt);;所有文件 (*)"
        )
        if path:
            self._menu_selected_path = path
            self._run_scan(path)
    elif chosen == add_folder:
        path = self._pick_folder(_("dialog_select_folder"))
        if path:
            self._menu_selected_path = path
            self._run_scan(path)
    elif chosen == remove_selected:
        self._remove_selected_rows()
    elif chosen == remove_all:
        self._clear_table()
        self._parsed_results.clear()
        self.status_changed.emit(_("status_workspace_cleared"))


# ── 离线查看 ──


def _on_offline_view(self) -> None:
    """从本地文件索引中查看标准完整信息（无需联网）。"""
    if not self._mgr_ready:
        return
    rows = {r.row() for r in self.work_table.selectedIndexes()}
    if not rows:
        return
    if not self._mgr.file_index:
        self.status_changed.emit(_("status_file_index_not_init"))
        return
    row = min(rows)
    if row >= len(self._parsed_results):
        return
    parsed = self._parsed_results[row]
    results = self._mgr.get_file_index_full_info(parsed.logical_code, parsed.number)
    if not results:
        QMessageBox.information(
            self, _("offline_view"), _("本地索引中未找到 {} 的相关信息").format(parsed.get_full_number())
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
    QMessageBox.information(self, _("offline_view"), "\n".join(lines))


# ── 删除选中行 ──


def _remove_selected_rows(self) -> None:
    """从工作区表格中移除选中的行（不删除物理文件）。"""
    rows = set()
    for item in self.work_table.selectedItems():
        rows.add(item.row())
    if not rows:
        return
    removed = 0
    for r in sorted(rows, reverse=True):
        self.work_table.removeRow(r)
        if r < len(self._parsed_results):
            del self._parsed_results[r]
        removed += 1
    self.status_changed.emit(f"已移除 {removed} 行")


# ── 添加表格行 ──


def _add_table_row(self, update: RowUpdate) -> None:
    """根据 RowUpdate 数据向工作区表格添加一行。"""
    logger.debug(
        "[TRACE-A] _add_table_row: 行号=%d 标准号=%r 标准名称=%r 工作状态=%r 生效状态=%r 是否采标=%s",
        update.seq,
        update.parsed.get_full_number(),
        update.std_name_override or update.parsed.std_name,
        update.work_status,
        update.effect_status,
        update.is_adopted,
    )
    row = self.work_table.rowCount()
    self.work_table.insertRow(row)
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
        self.work_table.setItem(row, c, item)


# ── 清空表格 ──


def _clear_table(self) -> None:
    """清空工作区表格所有行。"""
    self.work_table.setRowCount(0)


# ── 按序号查找行 ──


def _find_row_by_seq(self, seq: int) -> int:
    """根据序号在表格第一列中查找对应行索引，未找到返回 -1。"""
    for r in range(self.work_table.rowCount()):
        item = self.work_table.item(r, 0)
        if item and item.text() and int(item.text()) == seq:
            return r
    return -1


# ── 最小列宽强制 ──


def _enforce_min_column_width(self, col: int, _old: int, new: int) -> None:
    """确保列宽不小于预设最小值，并自动保存列宽到配置。"""
    if col in self._col_specs:
        mn = self._col_specs[col][1]
        if new < mn:
            self.work_table.horizontalHeader().resizeSection(col, mn)
    self._save_column_widths()


# ── 键盘事件 ──


def _table_key_press_event(self, event: Any) -> None:
    """处理表格键盘事件：Ctrl+C 复制选中单元格。"""
    if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
        self._copy_selected_cells()
    else:
        QTableWidget.keyPressEvent(self.work_table, event)


# ── 复制选中单元格 ──


def _copy_selected_cells(self) -> None:
    """将选中单元格内容以制表符分隔复制到剪贴板。"""
    selected = self.work_table.selectedIndexes()
    if not selected:
        return
    rows = sorted(set(i.row() for i in selected))
    cols = sorted(set(i.column() for i in selected))
    lines = []
    for r in rows:
        cells = []
        for c in cols:
            item = self.work_table.item(r, c)
            cells.append(item.text() if item else "")
        lines.append("\t".join(cells))
    QApplication.clipboard().setText("\n".join(lines))
