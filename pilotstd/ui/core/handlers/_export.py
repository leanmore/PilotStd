# pilotstd/ui/core/handlers/_export.py
"""ExportHandler — 导出文件列表/文件夹树/诊断报告，替代 ExportMixin。"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QDialog, QFileDialog, QTableWidget, QTextEdit, QWidget

from ....i18n import _
from ...dialogs import ExportFileListDialog
from ...table_constants import WORK_COLUMN_KEYS, WORK_COLUMNS

logger = logging.getLogger(__name__)


class ExportHandler:
    """导出文件列表/文件夹树/诊断报告。

    通过依赖注入替代多重继承，通过回调懒加载控件引用，
    不发射 Qt 信号，通过 _status 回调与上层通信。
    """

    MAX_FOLDER_DEPTH = 50  # 最大递归深度，防止符号链接循环或深层目录栈溢出

    def __init__(
        self,
        config: Any,  # ConfigManager
        status_callback: Callable[[str], None],
        get_selected_path: Callable[[], str],  # 获取当前选中路径
        get_parsed_results: Callable[[], list],  # 获取解析结果列表（用于诊断）
        get_work_table: Callable[[], QTableWidget],  # 获取工作表（用于诊断）
        get_log_view: Callable[[], QTextEdit],  # 获取日志视图（用于诊断）
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._status = status_callback
        self._get_selected_path = get_selected_path
        self._get_parsed_results = get_parsed_results
        self._get_work_table = get_work_table
        self._get_log_view = get_log_view
        self._parent = parent

    # ── 导出文件清单 ─────────────────────────────────────────

    def on_export_file_list(self) -> None:
        """导出文件名清单，可选是否包含路径名。"""
        # 获取默认路径（当前选中路径或桌面）
        path = self._get_selected_path()
        if not path:
            path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        dlg = ExportFileListDialog(self._parent, path)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        root = dlg.source_path
        include_path = dlg.include_path
        # 弹出保存文件对话框
        save_path, __ = QFileDialog.getSaveFileName(
            self._parent, "导出文件列表", "file_list.txt", "TXT (*.txt);;CSV (*.csv)"
        )
        if not save_path:
            return

        # 遍历目录收集文件名
        lines = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            # 跳过过期作废和 __pycache__ 目录
            dirnames[:] = [d for d in dirnames if d not in ("过期作废", "__pycache__")]
            for fn in filenames:
                try:
                    full = os.path.join(dirpath, fn)
                    if include_path:
                        lines.append(full)
                    else:
                        lines.append(fn)
                except OSError:
                    pass  # 单个文件名拼接失败，跳过

        with open(save_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._status(f"文件名清单已保存: {save_path} ({len(lines)} 项)")
        logger.info("导出文件清单: %s (%d 项)", save_path, len(lines))

    # ── 导出文件夹层次 ───────────────────────────────────────

    def on_export_folder_tree(self) -> None:
        """导出文件夹层次结构。"""
        # 获取默认路径
        path = self._get_selected_path()
        if not path:
            path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        if not os.path.isdir(path):
            return

        # 弹出保存对话框
        save_path, __ = QFileDialog.getSaveFileName(self._parent, "导出文件夹层次", "folder_tree.txt", "TXT (*.txt)")
        if not save_path:
            return

        # 递归收集树形结构
        lines = []
        self._collect_folder_tree(path, lines, prefix="")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._status(f"文件夹层次已保存: {save_path} ({len(lines)} 行)")
        logger.info("导出文件夹层次: %s (%d 行)", save_path, len(lines))

    def _collect_folder_tree(self, root: str, lines: list, prefix: str, depth: int = 0) -> None:
        """收集文件夹树形结构（防御性递归，有深度上限和符号链接保护）。"""
        if depth > self.MAX_FOLDER_DEPTH:
            lines.append(f"{prefix}... (超过最大深度 {self.MAX_FOLDER_DEPTH}，已截断)")
            return
        lines.append(f"{prefix}{os.path.basename(root) or root}")
        try:
            entries = sorted(os.scandir(root), key=lambda e: (not e.is_dir(), e.name.lower()))
        except (PermissionError, OSError):
            return
        count = 0
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if not is_dir:
                continue
            if entry.name.startswith(".") or entry.name in ("__pycache__", "过期作废"):
                continue
            count += 1
        idx = 0
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if not is_dir:
                continue
            if entry.name.startswith(".") or entry.name in ("__pycache__", "过期作废"):
                continue
            idx += 1
            connector = "├── " if idx < count else "└── "
            child_prefix = prefix + ("│   " if idx < count else "    ")
            lines.append(f"{prefix}{connector}{entry.name}")
            self._collect_folder_tree(entry.path, lines, child_prefix, depth + 1)

    # ── 导出诊断 ─────────────────────────────────────────────

    def on_export_diag(self) -> None:
        """导出诊断报告：配置 + 运行状态 + 完整日志。"""
        import platform
        from datetime import datetime

        # 弹出保存文件对话框，默认文件名含时间戳
        path, __ = QFileDialog.getSaveFileName(
            self._parent,
            "导出诊断报告",
            f"pilotstd_diag_{datetime.now():%Y%m%d_%H%M%S}.log",
            "LOG (*.log)",
        )
        if not path:
            return

        work_table = self._get_work_table()
        parsed_results = self._get_parsed_results()
        log_view = self._get_log_view()

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
            f.write(f"  解析结果: {len(parsed_results)} 条\n")
            f.write(f"  表格行数: {work_table.rowCount()} 行\n")
            hidden = [_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS)) if work_table.isColumnHidden(c)]
            f.write(f"  隐藏列: {hidden}\n")

            f.write("\n--- 运行日志 ---\n")
            f.write(log_view.toPlainText())

        self._status(f"诊断报告已导出: {path}")
        logger.info("导出诊断报告: %s", path)
