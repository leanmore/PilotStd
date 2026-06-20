# pilotstd/ui/pages/task_page.py
# 任务中心：历史记录、进度、日志

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
from ...task.models import TaskStatus
from ...task.queue import TaskQueue


class TaskPage(QWidget):
    """任务中心控件：展示任务列表和详情。"""

    def __init__(self, task_queue: TaskQueue | None = None):
        super().__init__()
        self._queue = task_queue
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上部：任务列表
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
        self.task_table.setColumnCount(6)
        self.task_table.setHorizontalHeaderLabels(
            [
                _("header_task_id"),
                _("header_task_type"),
                _("header_task_status"),
                _("header_task_progress"),
                _("header_task_created"),
                _("header_task_error"),
            ]
        )
        header = self.task_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        task_layout.addWidget(self.task_table)

        # 下部：详情
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

    def _refresh(self):
        self.task_table.setRowCount(0)
        if not self._queue:
            return
        tasks = self._queue.list_all(limit=100)
        for row, t in enumerate(tasks):
            self.task_table.insertRow(row)
            self.task_table.setItem(row, 0, QTableWidgetItem(t.task_id))
            self.task_table.setItem(row, 1, QTableWidgetItem(t.task_type.value))
            self.task_table.setItem(row, 2, QTableWidgetItem(t.status.value))
            self.task_table.setItem(
                row,
                3,
                QTableWidgetItem(
                    f"{t.completed_items}/{t.total_items} ({t.progress_pct:.0f}%)"
                ),
            )
            self.task_table.setItem(
                row, 4, QTableWidgetItem(t.updated_at[:19] if t.updated_at else "")
            )
            self.task_table.setItem(row, 5, QTableWidgetItem(t.error_log))

    def _clear_completed(self):
        if self._queue:
            for t in self._queue.list_all(limit=200):
                if t.status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.CANCELLED,
                    TaskStatus.FAILED,
                ):
                    self._queue.cancel(t.task_id)  # marks for cleanup
        self._refresh()


class TaskCenterDialog(QDialog):
    """任务中心对话框。"""

    def __init__(self, task_queue: TaskQueue | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("title_task_center"))
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        self.page = TaskPage(task_queue)
        layout.addWidget(self.page)

        btn_close = QPushButton(_("btn_close"))
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close)
