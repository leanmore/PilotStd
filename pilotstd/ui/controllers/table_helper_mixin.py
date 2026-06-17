# pilotstd/ui/controllers/table_helper_mixin.py
# 表格右键菜单、行操作、列宽管理 — 从 main_window.py 提取

import logging
from PyQt6.QtWidgets import (
    QMenu, QMessageBox, QFileDialog, QTableWidgetItem, QApplication,
)
from PyQt6.QtCore import Qt

from ...i18n import _
from ..table_mixin import WORK_COLUMNS
from ..workers import RowUpdate

logger = logging.getLogger(__name__)


class TableHelperMixin:
    """表格右键菜单、行操作、列宽管理。依赖 self.work_table, self._config, self._parsed_results。"""

    # ── 右键菜单 ─────────────────────────────────────────

    def _on_work_table_context_menu(self, pos):
        """工作表右键菜单：📋复制 | 📄增加文件 | 📁增加文件夹 | 🗑移除所选 | 🧹移除全部。

        菜单项文本通过 _() 国际化，emoji 图标在代码中统一添加。
        移除操作不删除物理文件，仅从工作区表格中清除行。
        """
        menu = QMenu(self)

        copy_action = menu.addAction(f"📋 {_('copy')}")
        copy_action.setToolTip("复制选中单元格内容至剪贴板")
        copy_action.triggered.connect(self._copy_selected_cells)

        menu.addSeparator()

        offline_action = menu.addAction(f"🔍 {_('offline_view')}")
        offline_action.setToolTip("从本地索引和缓存查看标准完整信息（无需联网）")
        offline_action.triggered.connect(self._on_offline_view)

        if not self.work_table.selectedItems():
            offline_action.setEnabled(False)

        add_file = menu.addAction(f"📄 {_('add_file')}")
        add_file.setToolTip("选择一个标准文件加入工作区")
        add_folder = menu.addAction(f"📁 {_('add_folder')}")
        add_folder.setToolTip("选择一个文件夹加入工作区")

        menu.addSeparator()

        remove_selected = menu.addAction(f"🗑 {_('remove_selected')}")
        remove_selected.setToolTip("从工作区表格中移除选中的行（不删除物理文件）")
        remove_all = menu.addAction(f"🧹 {_('remove_all')}")
        remove_all.setToolTip("清空工作区表格（不删除物理文件）")

        if self.work_table.rowCount() == 0:
            remove_selected.setEnabled(False)
            remove_all.setEnabled(False)
        if not self.work_table.selectedItems():
            remove_selected.setEnabled(False)

        chosen = menu.exec(self.work_table.viewport().mapToGlobal(pos))

        if chosen == add_file:
            path, _filter = QFileDialog.getOpenFileName(self, _("dialog_select_file"), "",
                                                        "标准文件 (*.pdf *.doc *.docx *.txt);;所有文件 (*)")
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
            self.status_changed.emit("已清空工作区")

    # ── 离线查看 ─────────────────────────────────────────

    def _on_offline_view(self):
        """离线查看：从本地索引和缓存联合查询标准信息。"""
        if not self._mgr_ready:
            return
        rows = {r.row() for r in self.work_table.selectedIndexes()}
        if not rows:
            return

        if not self._mgr.file_index:
            self.status_changed.emit("文件索引未初始化")
            return

        row = min(rows)
        if row >= len(self._parsed_results):
            return

        parsed = self._parsed_results[row]
        results = self._mgr.get_file_index_full_info(parsed.logical_code, parsed.number)

        if not results:
            QMessageBox.information(self, _("offline_view"),
                _("本地索引中未找到 {} 的相关信息").format(parsed.get_full_number()))
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

    # ── 行操作 ───────────────────────────────────────────

    def _remove_selected_rows(self):
        """移除表格中选中的行，同步更新 _parsed_results。"""
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

    def _add_table_row(self, update: RowUpdate):
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
            QTableWidgetItem(getattr(update.parsed, 'found_replaces', '')),
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

    def _clear_table(self):
        self.work_table.setRowCount(0)

    def _find_row_by_seq(self, seq: int) -> int:
        for r in range(self.work_table.rowCount()):
            item = self.work_table.item(r, 0)
            if item and item.text() and int(item.text()) == seq:
                return r
        return -1

    def _table_to_list(self) -> list:
        rows = []
        for r in range(self.work_table.rowCount()):
            row_data = {}
            for c in range(self.work_table.columnCount()):
                item = self.work_table.item(r, c)
                row_data[WORK_COLUMNS[c]] = item.text() if item else ""
            rows.append(row_data)
        return rows

    # ── 列宽管理 ─────────────────────────────────────────

    def _enforce_min_column_width(self, col: int, _old: int, new: int):
        if col in self._col_specs:
            mn = self._col_specs[col][1]
            if new < mn:
                self.work_table.horizontalHeader().resizeSection(col, mn)
        self._save_column_widths()

    def _save_column_widths(self):
        widths = [self.work_table.columnWidth(c) for c in range(self.work_table.columnCount())]
        self._config.set("ui.column_widths", widths)

    def _restore_column_widths(self):
        widths = self._config.get("ui.column_widths")
        if widths and len(widths) == self.work_table.columnCount():
            for c, w in enumerate(widths):
                if w > 0:
                    self.work_table.setColumnWidth(c, w)

    # ── 键盘交互 ─────────────────────────────────────────

    def _table_key_press_event(self, event):
        if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._copy_selected_cells()
        else:
            QTableWidget.keyPressEvent(self.work_table, event)

    def _copy_selected_cells(self):
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
        from PyQt6.QtWidgets import QApplication as QA
        QA.clipboard().setText("\n".join(lines))
