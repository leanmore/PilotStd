# 模块：项目//页面/_脚本
# 任务中心：我做过的 / 正在做的事（一行 = 一次用户操作）
# 分隔
# W1 改造要点：行单位从 task_id 改为"业务名 + 时间 + 结果"；状态折叠为用户语言 4 态；
# 结果列给出"成功 / 失败 / 跳过"；错误列改为"需要我做什么"的一句话，明细在下方展开。

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...i18n import _
from ...task.models import TaskInfo, TaskStatus, TaskType
from ...task.queue import TaskQueue

# 业务名（用户语言）：TaskType → i18n 键。
# desktop 写入方（`_dialog_ops._register_task`）目前只映射 4 类（无 expire），但本表覆盖
# 全部 5 类——否则新增写入方时会出现"未知类型"。
_BUSINESS_KEYS: dict[TaskType, str] = {
    TaskType.SCAN: "task_scan",
    TaskType.QUERY: "task_query",
    TaskType.DOWNLOAD: "task_download",
    TaskType.ORGANIZE: "task_normalize",
    TaskType.EXPIRE: "task_expire",
}

# 状态 → 用户语言 4 态：pending/running/paused 对用户都是"进行中"（减少术语）。
_STATUS_KEYS: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "task_status_running",
    TaskStatus.RUNNING: "task_status_running",
    TaskStatus.PAUSED: "task_status_running",
    TaskStatus.COMPLETED: "task_status_completed",
    TaskStatus.FAILED: "task_status_failed",
    TaskStatus.CANCELLED: "task_status_cancelled",
}

# 已结束的状态（"结果摘要"与"提示"只对它们有意义）
_FINISHED = (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

_COL_BUSINESS, _COL_STATUS, _COL_RESULT, _COL_TIME, _COL_HINT = range(5)


def business_name(task_type: TaskType) -> str:
    """任务类型的业务名（用户语言）。"""
    return _(_BUSINESS_KEYS.get(task_type, "task_unknown"))


def status_name(status: TaskStatus) -> str:
    """任务状态的用户语言（4 态）。"""
    return _(_STATUS_KEYS.get(status, "task_status_running"))


def result_summary(t: TaskInfo) -> str:
    """结果列：进行中给进度，已结束给"成功 / 失败 / 跳过"。

    跳过数按 `总数 - 成功 - 失败` 推导（`TaskInfo` 没有独立的 skipped 字段）；
    负数一律截到 0，避免写入方计数不一致时显示"跳过 -2"。
    """
    if t.status not in _FINISHED:
        return f"{t.completed_items}/{t.total_items} ({t.progress_pct:.0f}%)"
    skipped = max(0, t.total_items - t.completed_items - t.failed_items)
    return _("task_result_summary").format(
        ok=t.completed_items, failed=t.failed_items, skipped=skipped
    )


def action_hint(t: TaskInfo) -> str:
    """提示列："需要我做什么"。

    只按**状态**给建议，不解析 `error_log` 文本——文案一改就失准，且错误原文本来就在
    下方明细里可展开。
    """
    if t.status == TaskStatus.FAILED:
        return _("task_hint_failed")
    if t.status == TaskStatus.CANCELLED:
        return _("task_hint_cancelled")
    return ""


# ──：任务列表控件──


class TaskPage(QWidget):
    """任务中心控件：展示"我做过的 / 正在做的事"清单与明细。"""

    def __init__(self, task_queue: TaskQueue | None = None) -> None:
        super().__init__()
        self._queue = task_queue
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上部：操作清单
        task_widget = QWidget()
        task_layout = QVBoxLayout(task_widget)
        task_layout.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton(_("btn_refresh"))
        self.btn_refresh.clicked.connect(self._refresh)
        btn_layout.addWidget(self.btn_refresh)
        self.btn_clear = QPushButton(_("btn_clear_done"))
        self.btn_clear.clicked.connect(self._clear_completed)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        task_layout.addLayout(btn_layout)

        self.task_table = QTableWidget()
        self.task_table.setColumnCount(5)
        self.task_table.setHorizontalHeaderLabels(
            [
                _("header_task_business"),
                _("header_task_status"),
                _("header_task_result"),
                _("header_task_updated"),
                _("header_task_hint"),
            ]
        )
        header = self.task_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(_COL_HINT, QHeaderView.ResizeMode.Stretch)
        self.task_table.itemSelectionChanged.connect(self._on_selection_changed)
        task_layout.addWidget(self.task_table)

        # 下部：明细（选中某行后展开）
        detail_group = QGroupBox(_("task_detail_group"))
        detail_layout = QVBoxLayout(detail_group)
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setMaximumHeight(120)
        detail_layout.addWidget(self.detail_view)

        splitter.addWidget(task_widget)
        splitter.addWidget(detail_group)
        layout.addWidget(splitter)

        if self._queue:
            self._refresh()

    # ── 刷新清单 ──

    def _refresh(self) -> None:
        """从 TaskQueue 重新加载清单并填充表格（保持手动刷新：用户在桌前，无需轮询）。"""
        self.task_table.setRowCount(0)
        if not self._queue:
            return
        tasks = self._queue.list_all(limit=100)
        for row, t in enumerate(tasks):
            self.task_table.insertRow(row)
            self.task_table.setItem(row, _COL_BUSINESS, QTableWidgetItem(business_name(t.task_type)))
            self.task_table.setItem(row, _COL_STATUS, QTableWidgetItem(status_name(t.status)))
            self.task_table.setItem(row, _COL_RESULT, QTableWidgetItem(result_summary(t)))
            self.task_table.setItem(
                row, _COL_TIME, QTableWidgetItem(t.updated_at[:19] if t.updated_at else "")
            )
            self.task_table.setItem(row, _COL_HINT, QTableWidgetItem(action_hint(t)))

    # ── 明细展开 ──

    def _on_selection_changed(self) -> None:
        """选中行时把明细（业务/状态/结果/时间 + 错误与结果原文）展开到下方文本框。"""
        rows = self.task_table.selectionModel().selectedRows() if self.task_table.selectionModel() else []
        if not rows or not self._queue:
            self.detail_view.clear()
            return
        tasks = self._queue.list_all(limit=100)
        index = rows[0].row()
        if index >= len(tasks):
            self.detail_view.clear()
            return
        t = tasks[index]
        lines = [
            _("task_detail_summary").format(
                business=business_name(t.task_type),
                status=status_name(t.status),
                result=result_summary(t),
                time=t.updated_at[:19] if t.updated_at else "",
            )
        ]
        if t.error_log:
            lines.append(_("task_detail_error").format(error=t.error_log))
        if t.result_json:
            lines.append(_("task_detail_result").format(result=t.result_json))
        self.detail_view.setPlainText("\n".join(lines))

    # ── 清除已完成（真删，见 TaskQueue.clear_finished 的说明）──

    def _clear_completed(self) -> None:
        """清除已结束的任务记录（已完成 / 失败 / 已放弃）。"""
        if self._queue:
            self._queue.clear_finished()
        self.detail_view.clear()
        self._refresh()


# ──：任务中心对话框──


class TaskCenterDialog(QDialog):
    """任务中心对话框。"""

    def __init__(self, task_queue: TaskQueue | None = None, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("title_task_center"))
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        self.page = TaskPage(task_queue)
        layout.addWidget(self.page)

        btn_close = QPushButton(_("btn_close"))
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close)
