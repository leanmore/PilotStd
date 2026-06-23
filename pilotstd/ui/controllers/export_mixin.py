# pilotstd/ui/controllers/export_mixin.py
# 导出相关方法 — 从 main_window.py 提取

import logging
import os
from typing import Any

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QDialog, QFileDialog

from ...i18n import _
from ..dialogs import ExportFileListDialog
from ..table_mixin import WORK_COLUMN_KEYS, WORK_COLUMNS

logger = logging.getLogger(__name__)


class ExportMixin:
    """导出文件列表/文件夹树/诊断报告。依赖 self._config, self._get_selected_path()。"""

    # ── 导出文件清单 ─────────────────────────────────────────

    def _on_export_file_list(self) -> None:
        """导出文件名清单，可选是否包含路径名。"""
        path = self._get_selected_path()
        if not path:
            path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        dlg = ExportFileListDialog(self, path)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        root = dlg.source_path
        include_path = dlg.include_path
        save_path, __ = QFileDialog.getSaveFileName(self, "导出文件列表", "file_list.txt", "TXT (*.txt);;CSV (*.csv)")
        if not save_path:
            return

        lines = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ("过期作废", "__pycache__")]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if include_path:
                    lines.append(full)
                else:
                    lines.append(fn)

        with open(save_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.status_changed.emit(f"文件名清单已保存: {save_path} ({len(lines)} 项)")

    # ── 导出文件夹层次 ───────────────────────────────────────

    def _on_export_folder_tree(self) -> None:
        """导出文件夹层次结构。"""
        path = self._get_selected_path()
        if not path:
            path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        if not os.path.isdir(path):
            return

        save_path, __ = QFileDialog.getSaveFileName(self, "导出文件夹层次", "folder_tree.txt", "TXT (*.txt)")
        if not save_path:
            return

        lines = []
        self._collect_folder_tree(path, lines, prefix="")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.status_changed.emit(f"文件夹层次已保存: {save_path} ({len(lines)} 行)")

    def _collect_folder_tree(self, root: str, lines: list[Any], prefix: str) -> None:
        """递归收集文件夹树形结构。"""
        lines.append(f"{prefix}{os.path.basename(root) or root}")
        try:
            entries = sorted(os.scandir(root), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        count = 0
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name in ("__pycache__", "过期作废"):
                continue
            count += 1
        idx = 0
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name in ("__pycache__", "过期作废"):
                continue
            idx += 1
            connector = "├── " if idx < count else "└── "
            child_prefix = prefix + ("│   " if idx < count else "    ")
            lines.append(f"{prefix}{connector}{entry.name}")
            self._collect_folder_tree(entry.path, lines, child_prefix)

    # ── 导出诊断 ─────────────────────────────────────────────

    def _on_export_diag(self) -> None:
        """导出诊断报告：配置 + 运行状态 + 完整日志。"""
        import platform
        from datetime import datetime

        path, __ = QFileDialog.getSaveFileName(
            self,
            "导出诊断报告",
            f"pilotstd_diag_{datetime.now():%Y%m%d_%H%M%S}.log",
            "LOG (*.log)",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write("=== PilotStd 诊断报告 ===\n")
            f.write(f"时间: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"Python: {platform.python_version()} | {platform.system()} {platform.release()}\n\n")

            f.write("--- 配置 ---\n")
            for key in [
                "storage.root_dir",
                "query.use_cache",
                "query.site_order",
                "appearance.theme",
                "appearance.column_visibility",
                "scan.skip_folders",
                "scan.extensions",
            ]:
                f.write(f"  {key}: {self._config.get(key, 'N/A')}\n")

            f.write("\n--- 工作区 ---\n")
            f.write(f"  解析结果: {len(self._parsed_results)} 条\n")
            f.write(f"  表格行数: {self.work_table.rowCount()} 行\n")
            f.write(
                f"  隐藏列: {[_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS)) if self.work_table.isColumnHidden(c)]}\n"  # noqa: E501
            )

            f.write("\n--- 运行日志 ---\n")
            f.write(self.log_view.toPlainText())

        self.status_changed.emit(f"诊断报告已导出: {path}")
