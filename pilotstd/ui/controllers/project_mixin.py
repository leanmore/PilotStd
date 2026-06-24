# pilotstd/ui/controllers/project_mixin.py
# 项目打开/恢复/保存 — 从 main_window.py 提取

import logging
import os
from typing import Any

from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QTableWidgetItem,
)

from ...i18n import _
from ..table_mixin import WORK_COLUMN_KEYS, WORK_COLUMNS

logger = logging.getLogger(__name__)


class ProjectMixin:
    """项目打开/恢复/保存操作。依赖 self._project, self._config, self.work_table,
    self._collect_state(), self._clear_table(), self._navigate_to()。
    """

    # ── 打开项目 ─────────────────────────────────────────

    def _on_open_project(self) -> None:
        path, __ = QFileDialog.getOpenFileName(self, _("dialog_open_project"), "", _("file_filter_project"))
        if not path:
            return
        state = self._project.load(path)
        if state is None:
            QMessageBox.warning(self, _("open_failed"), _("cant_read_project").format(path))
            return
        self._restore_state(state)
        self.status_changed.emit(_("project_loaded").format(path))

    def _restore_state(self, state: dict[str, Any]) -> None:
        rows = state.get("work_table_rows", [])
        saved_path = state.get("current_path", "")
        self._clear_table()
        for i, row_data in enumerate(rows):
            row = self.work_table.rowCount()
            self.work_table.insertRow(row)
            for c, col_name in enumerate(WORK_COLUMNS):
                # 先用原始中文键名取值，回退到翻译键名（兼容未来格式）
                value = row_data.get(col_name, "")
                if not value:
                    translated = _(WORK_COLUMN_KEYS[c])
                    if translated != col_name:
                        value = row_data.get(translated, "")
                self.work_table.setItem(row, c, QTableWidgetItem(value))
        if saved_path and os.path.exists(saved_path):
            self._navigate_to(saved_path)
        # 恢复未识别文件列表（只保留磁盘上仍然存在的文件，避免已删除/已搬迁的条目残留）
        unrecognized = state.get("unrecognized_files", [])
        if unrecognized:
            self._unrecognized_files = [f for f in unrecognized if os.path.exists(f)]

    # ── 保存项目 ─────────────────────────────────────────

    def _on_save_query_project(self) -> None:
        self._save_project_dialog(_("save_query_project"))

    def _on_save_download_project(self) -> None:
        self._save_project_dialog(_("save_download_project"))

    def _save_project_dialog(self, label: str) -> None:
        path, __ = QFileDialog.getSaveFileName(None, label, "project.pilotstd", _("file_filter_project"))
        if path:
            state = self._collect_state()
            ok = self._project.save(path, state)
            if ok:
                self.status_changed.emit(_("project_save_success").format(label=label, path=path))
            else:
                QMessageBox.warning(
                    self,
                    _("title_save_failed"),
                    _("msg_save_project_failed").format(path=path),
                )
