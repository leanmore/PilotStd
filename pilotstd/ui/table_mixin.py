# pilotstd/ui/table_mixin.py
# 工作表 Mixin：列可见性 + 导出过滤（新增功能，不重构现有方法）

import csv
import logging

from PyQt6.QtWidgets import QMenu, QMessageBox, QFileDialog

from ..i18n import _

logger = logging.getLogger(__name__)

WORK_COLUMNS = ["序号", "工作状态", "标准编号", "标准名称",
                "生效状态", "替代标准", "发布日期", "实施日期", "发布部门", "采标"]
WORK_COLUMN_KEYS = ["col_seq", "col_work_status", "col_std_number", "col_std_name",
                     "col_effect_status", "col_replaces", "col_publish_date",
                     "col_impl_date", "col_responsible_dept", "col_adopted"]
TOGGLEABLE_COLS = [4, 5, 6, 7, 8, 9]


class TableMixin:
    """列可见性 + 导出过滤。依赖 self.work_table, self._config, self._parsed_results"""

    # ── 列可见性 ─────────────────────────────────────────

    def _get_column_visibility(self) -> list:
        return [not self.work_table.isColumnHidden(c)
                for c in range(len(WORK_COLUMNS))]

    def _apply_column_visibility(self, visible: list):
        header = self.work_table.horizontalHeader()
        for c in range(len(WORK_COLUMNS)):
            if c < 4:
                self.work_table.setColumnHidden(c, False)
            elif c < len(visible):
                hidden = not visible[c]
                self.work_table.setColumnHidden(c, hidden)
                if hidden:
                    header.resizeSection(c, 0)
                elif hasattr(self, '_col_specs') and c in self._col_specs:
                    header.resizeSection(c, self._col_specs[c][0])

    def _save_column_visibility(self):
        self._config.set("appearance.column_visibility", self._get_column_visibility())

    def _load_column_visibility(self):
        default = [True] * len(WORK_COLUMNS)
        visible = self._config.get("appearance.column_visibility", default) or default
        self._apply_column_visibility(visible)

    def _on_header_context_menu(self, pos):
        header = self.work_table.horizontalHeader()
        menu = QMenu(self)
        for c in TOGGLEABLE_COLS:
            action = menu.addAction(_(WORK_COLUMN_KEYS[c]))
            action.setCheckable(True)
            action.setChecked(not self.work_table.isColumnHidden(c))
            action.setData(c)
        chosen = menu.exec(header.viewport().mapToGlobal(pos))
        if chosen:
            c = chosen.data()
            hidden = not self.work_table.isColumnHidden(c)
            self.work_table.setColumnHidden(c, hidden)
            if hidden:
                header.resizeSection(c, 0)
            elif hasattr(self, '_col_specs') and c in self._col_specs:
                header.resizeSection(c, self._col_specs[c][0])
            self._save_column_visibility()

    def _get_visible_cols(self) -> list:
        """返回可见列的翻译后显示名（用于导出文件表头和UI提示）。"""
        return [_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS))
                if not self.work_table.isColumnHidden(c)]

    # ── 导出（覆盖 main_window 的同名方法） ────────────────

    def _on_save_result(self, fmt: str):
        if self.work_table.rowCount() == 0:
            QMessageBox.information(self, _("title_hint"), _("no_data_to_save"))
            return

        vis_names = self._get_visible_cols()
        hidden = [_(WORK_COLUMN_KEYS[c]) for c in range(4, len(WORK_COLUMNS))
                  if self.work_table.isColumnHidden(c)]
        if hidden:
            msg = _("msg_export_hidden_warning").format(
                hidden_count=len(hidden), hidden_list=', '.join(hidden),
                visible_count=len(vis_names))
            reply = QMessageBox.question(self, _("title_export_hint"), msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            reply.button(QMessageBox.StandardButton.Yes).setText(_("btn_yes"))
            reply.button(QMessageBox.StandardButton.No).setText(_("btn_no"))
            if reply != QMessageBox.StandardButton.Yes:
                return

        ext_map = {"txt": "TXT (*.txt)", "csv": "CSV (*.csv)"}
        path, __ = QFileDialog.getSaveFileName(
            self, _("dialog_save_sheet"), f"results.{fmt}", ext_map.get(fmt, "All (*)"))
        if not path:
            return

        rows = self._table_to_list()
        # 计算可见列的数据键名（用于行数据查找）
        visible_data_keys = [WORK_COLUMNS[c] for c in range(len(WORK_COLUMNS))
                            if not self.work_table.isColumnHidden(c)]
        try:
            if fmt == "txt":
                self._save_txt(path, rows, vis_names, visible_data_keys)
            elif fmt == "csv":
                self._save_csv(path, rows, vis_names, visible_data_keys)
        except OSError as e:
            QMessageBox.warning(self, _("title_save_failed"), str(e))

    def _save_txt(self, path: str, rows: list, cols: list = None,
                  data_keys: list = None):
        """保存TXT文件。cols为显示列名（表头），data_keys为数据键名（行查找）。"""
        if cols is None:
            cols = [_(k) for k in WORK_COLUMN_KEYS]
            data_keys = list(WORK_COLUMNS)
        elif data_keys is None:
            # 兼容旧调用：cols 同时用于表头和数据查找
            data_keys = cols
        widths = [len(c) for c in cols]
        for row in rows:
            for i, k in enumerate(data_keys):
                widths[i] = max(widths[i], len(str(row.get(k, ""))))
        with open(path, "w", encoding="utf-8") as f:
            header = "\t".join(c.ljust(widths[i]) for i, c in enumerate(cols))
            f.write(header + "\n")
            for row in rows:
                line = "\t".join(str(row.get(k, "")).ljust(widths[i]) for i, k in enumerate(data_keys))
                f.write(line + "\n")

    def _save_csv(self, path: str, rows: list, cols: list = None,
                  data_keys: list = None):
        """保存CSV文件。cols为显示列名（表头），data_keys为数据键名（行查找）。"""
        if cols is None:
            cols = [_(k) for k in WORK_COLUMN_KEYS]
            data_keys = list(WORK_COLUMNS)
        elif data_keys is None:
            # 兼容旧调用：cols 同时用于表头和数据查找
            data_keys = cols
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            # 先写翻译后的表头，再写数据行（数据行仍使用 WORK_COLUMNS 键名）
            w = csv.writer(f)
            w.writerow(cols)
            for row in rows:
                w.writerow([row.get(k, "") for k in data_keys])
