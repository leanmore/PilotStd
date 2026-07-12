# pilotstd/ui/core/handlers/_dialog.py
"""DialogHandler — 通用确认对话框、阶段完成弹窗、任务注册，替代 DialogMixin。"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _

logger = logging.getLogger(__name__)


class DialogHandler:
    """通用确认对话框、阶段完成弹窗、任务注册。

    通过依赖注入替代多重继承，不持有 UI 控件引用，parent 仅作为弹窗父控件。
    """

    def __init__(
        self,
        config: Any,  # ConfigManager
        mgr: Any,  # StandardManager（任务注册需要 task_queue）
        is_suppressed: Optional[Callable[[], bool]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._mgr = mgr
        self._is_suppressed = is_suppressed
        self._parent = parent

    # ── 通用确认对话框 ───────────────────────────────────

    def question_dlg(self, title: str, msg: str) -> QMessageBox.StandardButton:
        """弹出 i18n 化的是/否对话框。"""
        dlg = QMessageBox(self._parent)
        dlg.setWindowTitle(title)
        dlg.setText(msg)
        dlg.setIcon(QMessageBox.Icon.Question)
        btn_yes = dlg.addButton(_("btn_yes"), QMessageBox.ButtonRole.YesRole)
        dlg.addButton(_("btn_no"), QMessageBox.ButtonRole.NoRole)
        dlg.exec()
        return QMessageBox.StandardButton.Yes if dlg.clickedButton() == btn_yes else QMessageBox.StandardButton.No

    # ── 阶段前置条件对话框 ──────────────────────────────
    # 返回值: "run_prereq" — 执行前置阶段, "skip" — 跳过检查强制执行, "cancel" — 取消

    def stage_prereq_dialog(self, title: str, msg: str, prereq_label: str = "") -> str:
        """阶段依赖检查三按钮对话框。prereq_label 为前置操作的按钮文字。"""
        if self._is_suppressed and self._is_suppressed():
            return "skip"  # 自动运行模式：跳过检查强制执行
        dlg = QMessageBox(self._parent)
        dlg.setWindowTitle(title)
        dlg.setText(msg)
        dlg.setIcon(QMessageBox.Icon.Warning)
        btn_prereq = dlg.addButton(prereq_label or _("btn_run_prereq"), QMessageBox.ButtonRole.AcceptRole)
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

    def show_stage_dialog(
        self,
        title: str,
        message: str,
        next_action: Optional[Callable[[], None]] = None,
        next_label: str = "",
    ) -> None:
        """统一阶段弹窗。内容较长时自动出现垂直滚动条。"""
        dlg = QDialog(self._parent)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(400)
        dlg.resize(600, 500)
        dlg.setSizeGripEnabled(False)  # Windows 深色主题下会渲染为右下角像素方块
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(dlg)
        # 内容区域 — 包裹在 QScrollArea 中，内容超长时可滚动
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        container_layout.addWidget(label)
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
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

    def show_stage_dialog_multi(
        self,
        title: str,
        message: str,
        actions: list[tuple[str, Callable[..., Any]]],
    ) -> None:
        """多按钮阶段弹窗。内容较长时自动出现垂直滚动条。"""
        if self._is_suppressed and self._is_suppressed():
            return
        dlg = QDialog(self._parent)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(400)
        dlg.resize(600, 500)
        dlg.setSizeGripEnabled(False)  # Windows 深色主题下会渲染为右下角像素方块
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(dlg)
        # 内容区域 — 包裹在 QScrollArea 中，内容超长时可滚动
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        container_layout.addWidget(label)
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
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

    def register_task(self, label: str, total: int, completed: int, failed: int = 0) -> None:
        """向任务队列注册一条操作记录。"""
        try:
            from ....task.models import TaskType

            type_map = {
                "扫描": TaskType.SCAN,
                "查询": TaskType.QUERY,
                "下载": TaskType.DOWNLOAD,
                "规范化": TaskType.ORGANIZE,
            }
            task = self._mgr.task_queue.enqueue(type_map.get(label, TaskType.SCAN), total_items=total)
            self._mgr.task_queue.update_progress(task, completed=completed, failed=failed)
            logger.debug("任务记录: %s %d/%d", label, completed, total)
        except Exception as e:
            logger.warning("任务记录失败: %s", e)
