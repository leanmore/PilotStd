# 模块：项目//核心/处理器/_脚本
"""ProjectHandler — 项目打开/恢复/保存，替代 ProjectMixin。"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtWidgets import QFileDialog, QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

from ....i18n import _
from .project_flow_engine import ProjectFlowEngine

logger = logging.getLogger(__name__)


class ProjectHandler:
    """项目打开/恢复/保存操作。

    通过依赖注入替代 Mixin 继承，不直接持有 UI 控件。
    """

    def __init__(
        self,
        config: Any,
        project: Any,
        status_callback: Callable[[str], None],
        clear_table: Callable[[], None],
        add_row_from_dict: Callable[[dict], None],
        navigate_to: Callable[[str], None],
        get_work_state: Callable[[], dict],
        set_unrecognized_files: Callable[[list[str]], None],
        parent: QWidget | None = None,
    ) -> None:
        self._config = config
        self._project = project
        self._status = status_callback
        self._clear_table = clear_table
        self._add_row_from_dict = add_row_from_dict
        self._navigate_to = navigate_to
        self._get_work_state = get_work_state
        self._set_unrecognized_files = set_unrecognized_files
        self._parent = parent
        self._engine = ProjectFlowEngine()

    # ── 打开项目 ─────────────────────────────────────────────

    def on_open_project(self) -> None:
        """打开 .pilotstd 项目文件并恢复状态。"""
        path, _filter = QFileDialog.getOpenFileName(
            self._parent,
            _("dialog_open_project"),
            "",
            _("file_filter_project"),
        )
        if not path:
            return
        state = self._project.load(path)
        if state is None:
            QMessageBox.warning(
                self._parent,
                _("open_failed"),
                _("cant_read_project").format(path),
            )
            return
        self.restore_state(state)
        self._status(_("project_loaded").format(path))

    def restore_state(self, state: dict) -> None:
        """恢复项目状态（表格行 + 当前路径 + 未识别文件）。"""
        data = self._engine.deserialize_project_state(state)
        rows = data.get("work_table_rows", [])
        saved_path = data.get("current_path", "")
        self._clear_table()
        for row_data in rows:
            self._add_row_from_dict(row_data)
        if saved_path and os.path.exists(saved_path):
            self._navigate_to(saved_path)
        # 恢复未识别文件列表（只保留磁盘上仍然存在的文件）
        unrecognized = data.get("unrecognized_files", [])
        if unrecognized:
            self._set_unrecognized_files([f for f in unrecognized if os.path.exists(f)])

    # ── 保存项目 ─────────────────────────────────────────────

    def on_save_query_project(self) -> None:
        """保存查询项目。"""
        self._save_project_dialog(_("save_query_project"))

    def on_save_download_project(self) -> None:
        """保存下载项目。"""
        self._save_project_dialog(_("save_download_project"))

    def _save_project_dialog(self, label: str) -> None:
        """通用保存对话框：选择路径 → 收集状态 → 写入文件。"""
        path, _filter = QFileDialog.getSaveFileName(
            None,
            label,
            "project.pilotstd",
            _("file_filter_project"),
        )
        if not path:
            return
        state = self._get_work_state()
        ok = self._project.save(path, state)
        if ok:
            self._status(_("project_save_success").format(label=label, path=path))
        else:
            QMessageBox.warning(
                self._parent,
                _("title_save_failed"),
                _("msg_save_project_failed").format(path=path),
            )
