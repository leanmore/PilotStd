# pilotstd/ui/core/handlers/_file_dialog.py
"""FileDialogHandler — 文件/文件夹选择对话框，替代 FileDialogMixin。"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Callable, Optional

from PyQt6.QtWidgets import QFileDialog, QWidget

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FileDialogHandler:
    """文件/文件夹选择对话框。

    通过依赖注入替代多重继承，不持有 _menu_selected_path 状态，
    不发射 Qt 信号，通过回调与上层通信。
    """

    def __init__(
        self,
        config: Any,  # ConfigManager
        status_callback: Callable[[str], None],
        run_scan_callback: Callable[[str], None],  # 触发扫描
        get_selected_path_callback: Callable[[], str],  # 获取当前选中路径
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._status = status_callback
        self._run_scan = run_scan_callback
        self._get_selected_path = get_selected_path_callback
        self._parent = parent

    # ── 打开文件 ─────────────────────────────────────────────

    def on_open_file(self) -> None:
        """选择单个文件 → 触发扫描。"""
        path, _ = QFileDialog.getOpenFileName(
            self._parent, "选择文件", "", "标准文件 (*.pdf *.doc *.docx *.txt);;所有文件 (*)"
        )
        if path:
            logger.info("打开文件: %s", path)
            self._status(f"已选择文件: {os.path.basename(path)}")
            # 扫描方法内部会处理路径存储和状态更新
            self._run_scan(path)

    # ── 打开文件夹 ───────────────────────────────────────────

    def on_open_folder(self) -> None:
        """选择文件夹 → 触发扫描。"""
        last = self._config.get("appearance.last_import_path", "")
        path = self.pick_folder("选择文件夹", last)
        if path:
            self._config.set("appearance.last_import_path", path)
            self._config.save()
            logger.info("打开文件夹: %s", path)
            self._status(f"已选择文件夹: {path}")
            self._run_scan(path)

    # ── 工具栏导入 ───────────────────────────────────────────

    def on_select(self) -> None:
        """工具栏导入 → 选择文件夹 → 触发扫描。"""
        last = self._config.get("appearance.last_import_path", "")
        path = self.pick_folder("选择文件夹", last)
        if path:
            self._config.set("appearance.last_import_path", path)
            self._config.save()
            logger.info("选择: %s", path)
            self._status(f"已选择: {path}")
            self._run_scan(path)

    # ── 文件夹选择工具 ───────────────────────────────────────

    def pick_folder(self, title: str, start_dir: str = "") -> str:
        """打开系统原生文件夹选择对话框。"""
        return QFileDialog.getExistingDirectory(self._parent, title, start_dir)
