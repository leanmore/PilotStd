# pilotstd/ui/controllers/dialog_mixin.py
# 通用确认对话框 + 阶段完成弹窗 + 任务注册 — 从 main_window.py 提取

import logging
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...i18n import _

logger = logging.getLogger(__name__)


class DialogMixin:
    """通用确认对话框、阶段完成弹窗、任务注册。依赖 self._mgr.task_queue,
    self._suppress_dialogs, self.status_changed。
    """

    # ── 通用确认对话框 ───────────────────────────────────

    def _question_dlg(self, title: str, msg: str) -> QMessageBox.StandardButton:
        """弹出 i18n 化的是/否对话框。"""
        dlg = QMessageBox(self)  # type: ignore[call-overload]
        dlg.setWindowTitle(title)
        dlg.setText(msg)
        dlg.setIcon(QMessageBox.Icon.Question)
        btn_yes = dlg.addButton(_("btn_yes"), QMessageBox.ButtonRole.YesRole)
        dlg.addButton(_("btn_no"), QMessageBox.ButtonRole.NoRole)
        dlg.exec()
        return (
            QMessageBox.StandardButton.Yes
            if dlg.clickedButton() == btn_yes
            else QMessageBox.StandardButton.No
        )

    # ── 阶段前置条件对话框 ──────────────────────────────
    # 返回值: "run_prereq" — 执行前置阶段, "skip" — 跳过检查强制执行, "cancel" — 取消

    def _stage_prereq_dialog(self, title: str, msg: str, prereq_label: str = "") -> str:
        """阶段依赖检查三按钮对话框。prereq_label 为前置操作的按钮文字。"""
        if self._suppress_dialogs:
            return "skip"  # 自动运行模式：跳过检查强制执行
        dlg = QMessageBox(self)  # type: ignore[call-overload]
        dlg.setWindowTitle(title)
        dlg.setText(msg)
        dlg.setIcon(QMessageBox.Icon.Warning)
        btn_prereq = dlg.addButton(
            prereq_label or _("btn_run_prereq"), QMessageBox.ButtonRole.AcceptRole
        )
        btn_skip = dlg.addButton(_("btn_skip_prereq"), QMessageBox.ButtonRole.NoRole)
        dlg.addButton(_("btn_cancel"), QMessageBox.ButtonRole.RejectRole)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked == btn_prereq:
            return "run_prereq"
        if clicked == btn_skip:
            return "skip"
        return "cancel"

    # ── 阶段弹窗 ─────────────────────────────────────────

    def _show_stage_dialog(
        self, title: str, message: str, next_action=None, next_label: str = ""
    ):
        """统一阶段弹窗。下一步按钮在左，确定在右，等宽等高。
        支持右下角拉伸手柄调整窗口大小。"""
        dlg = QDialog(self)  # type: ignore[arg-type]
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(400)
        dlg.resize(600, 500)  # 合理的初始尺寸
        dlg.setSizeGripEnabled(True)
        layout = QVBoxLayout(dlg)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        if next_action:
            next_btn = QPushButton(next_label)
            next_btn.clicked.connect(lambda: [dlg.accept(), next_action()])  # type: ignore[func-returns-value]
            btn_layout.addWidget(next_btn)
        close_btn = QPushButton(_("btn_close"))
        close_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dlg.exec()

    def _show_stage_dialog_multi(
        self, title: str, message: str, actions: list[tuple[str, Callable]]
    ):
        """多按钮阶段弹窗。actions 为 [(按钮文本, 回调函数), ...] 列表。"""
        if self._suppress_dialogs:
            return
        dlg = QDialog(self)  # type: ignore[arg-type]
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(400)
        dlg.resize(600, 500)
        dlg.setSizeGripEnabled(True)
        layout = QVBoxLayout(dlg)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        for label_text, callback in actions:
            btn = QPushButton(label_text)
            btn.clicked.connect(lambda checked, cb=callback: [dlg.accept(), cb()])  # type: ignore[func-returns-value]
            btn_layout.addWidget(btn)
        close_btn = QPushButton(_("btn_close"))
        close_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dlg.exec()

    # ── 任务注册 ─────────────────────────────────────────

    def _register_task(self, label: str, total: int, completed: int, failed: int = 0):
        """向任务队列注册一条操作记录。"""
        try:
            from ...task.models import TaskType

            type_map = {
                "扫描": TaskType.SCAN,
                "查询": TaskType.QUERY,
                "下载": TaskType.DOWNLOAD,
                "规范化": TaskType.ORGANIZE,
            }
            task = self._mgr.task_queue.enqueue(
                type_map.get(label, TaskType.SCAN), total_items=total
            )
            self._mgr.task_queue.update_progress(
                task, completed=completed, failed=failed
            )
            logger.debug(f"任务记录: {label} {completed}/{total}")
        except Exception as e:
            logger.warning(f"任务记录失败: {e}")
