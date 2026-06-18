# pilotstd/ui/controllers/file_dialog_mixin.py
# 文件/文件夹选择对话框 — 从 main_window.py 提取

import logging
import os

from PyQt6.QtWidgets import QFileDialog

logger = logging.getLogger(__name__)


class FileDialogMixin:
    """文件/文件夹选择对话框。依赖 self._config, self._menu_selected_path,
    self.status_changed, self._run_scan()。
    """

    # ── 打开文件 ─────────────────────────────────────────

    def _on_open_file(self):
        path, __ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "标准文件 (*.pdf *.doc *.docx *.txt);;所有文件 (*)"
        )
        if path:
            self._menu_selected_path = path
            self.status_changed.emit(f"已选择文件: {os.path.basename(path)}")
            logger.info(f"打开文件: {path}")
            self._run_scan(path)

    # ── 打开文件夹 ───────────────────────────────────────

    def _on_open_folder(self):
        last = self._config.get("appearance.last_import_path", "")
        path = self._pick_folder("选择文件夹", last)
        if path:
            self._menu_selected_path = path
            self._config.set("appearance.last_import_path", path)
            self._config.save()
            self.status_changed.emit(f"已选择文件夹: {path}")
            logger.info(f"打开文件夹: {path}")
            self._run_scan(path)

    # ── 工具栏导入 ───────────────────────────────────────

    def _on_select(self):
        """导入文件夹到项目。"""
        last = self._config.get("appearance.last_import_path", "")
        path = self._pick_folder("选择文件夹", last)
        if path:
            self._menu_selected_path = path
            self._config.set("appearance.last_import_path", path)
            self._config.save()
            self.status_changed.emit(f"已选择: {path}")
            logger.info(f"选择: {path}")
            self._run_scan(path)

    # ── 文件夹选择工具 ───────────────────────────────────

    def _pick_folder(self, title: str, start_dir: str = "") -> str:
        """打开系统原生文件夹选择对话框。"""
        return QFileDialog.getExistingDirectory(self, title, start_dir)
