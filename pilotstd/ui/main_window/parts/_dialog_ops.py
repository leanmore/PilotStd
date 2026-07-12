"""Extracted dialog/progress methods for MainWindow."""

from __future__ import annotations

import logging
from typing import Any

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

logger = logging.getLogger("pilotstd.ui")


def _question_dlg(self, title: str, msg: str) -> QMessageBox.StandardButton:
    dlg = QMessageBox(self)  # type: ignore[call-overload]
    dlg.setWindowTitle(title)
    dlg.setText(msg)
    dlg.setIcon(QMessageBox.Icon.Question)
    btn_yes = dlg.addButton(_("btn_yes"), QMessageBox.ButtonRole.YesRole)
    dlg.addButton(_("btn_no"), QMessageBox.ButtonRole.NoRole)
    dlg.exec()
    return QMessageBox.StandardButton.Yes if dlg.clickedButton() == btn_yes else QMessageBox.StandardButton.No


def _stage_prereq_dialog(self, title: str, msg: str, prereq_label: str = "") -> str:
    if self._suppress_dialogs:
        return "skip"
    dlg = QMessageBox(self)  # type: ignore[call-overload]
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


def _show_stage_dialog(self, title: str, message: str, next_action: Any = None, next_label: str = "") -> None:
    dlg = QDialog(self)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(400)
    dlg.resize(600, 500)
    dlg.setSizeGripEnabled(False)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    layout = QVBoxLayout(dlg)
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


def _register_task(self, label: str, total: int, completed: int, failed: int = 0) -> None:
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
    except Exception as e:
        logger.warning("任务记录失败: %s", e)


def _on_raw_progress(self, cur: int, total: int) -> None:
    if total > 0:
        self._target_progress = (cur / total) * 100
    else:
        self._target_progress = 0
    if not self._progress_timer.isActive():
        self._progress_timer.start()


def _animate_progress(self) -> None:
    diff = self._target_progress - self._current_progress
    if abs(diff) < 0.5:
        self._current_progress = self._target_progress
        self.progress_changed.emit(int(self._current_progress))
        self._progress_timer.stop()
    else:
        self._current_progress += diff * 0.2
        self.progress_changed.emit(int(self._current_progress))


def _reset_progress_bar(self) -> None:
    self._progress_timer.stop()
    self._target_progress = 0
    self._current_progress = 0.0
    self.progress_changed.emit(0)


def _force_finish_progress(self) -> None:
    self._progress_timer.stop()
    self._target_progress = 100
    self._current_progress = 100.0
    self.progress_changed.emit(100)
