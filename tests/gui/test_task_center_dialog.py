# tests/gui/test_task_center_dialog.py
# TaskCenterDialog 测试 — 任务中心对话框

from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton


class TestTaskCenterDialog:
    """任务中心对话框测试。"""

    @pytest.fixture
    def mock_queue(self) -> MagicMock:
        """创建 mock TaskQueue，返回空任务列表。"""
        q = MagicMock()
        q.list_all.return_value = []
        return q

    def test_create_dialog_no_queue(self, qtbot) -> None:
        """不带 TaskQueue 创建对话框，标题和尺寸正确。"""
        from pilotstd.ui.pages.task_page import TaskCenterDialog

        dlg = TaskCenterDialog()
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "任务中心"
        assert dlg.width() >= 600

    def test_create_dialog_with_queue(self, qtbot, mock_queue) -> None:
        """带 TaskQueue 创建对话框，page 包含 queue 引用。"""
        from pilotstd.ui.pages.task_page import TaskCenterDialog

        dlg = TaskCenterDialog(mock_queue)
        qtbot.addWidget(dlg)
        assert dlg.page._queue is mock_queue

    def test_close_button_rejects(self, qtbot, mock_queue) -> None:
        """点击关闭按钮触发 reject。"""
        from pilotstd.ui.pages.task_page import TaskCenterDialog

        dlg = TaskCenterDialog(mock_queue)
        qtbot.addWidget(dlg)
        dlg.show()

        for btn in dlg.findChildren(QPushButton):
            if btn.text() == "关闭":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break
        assert dlg.result() == 0  # QDialog.Rejected

    def test_dialog_contains_task_page(self, qtbot, mock_queue) -> None:
        """对话框包含 TaskPage 控件。"""
        from pilotstd.ui.pages.task_page import TaskCenterDialog, TaskPage

        dlg = TaskCenterDialog(mock_queue)
        qtbot.addWidget(dlg)
        assert isinstance(dlg.page, TaskPage)


class TestTaskPage:
    """TaskPage 控件测试。"""

    @pytest.fixture
    def mock_queue_with_tasks(self) -> MagicMock:
        """创建 mock TaskQueue，返回示例任务列表。"""
        from pilotstd.task.models import TaskStatus, TaskType

        task = MagicMock()
        task.task_id = "task-001"
        task.task_type = TaskType.QUERY
        task.status = TaskStatus.COMPLETED
        task.completed_items = 5
        task.total_items = 5
        task.progress_pct = 100.0
        task.updated_at = "2024-01-15T10:30:00.000000"
        task.error_log = ""

        q = MagicMock()
        q.list_all.return_value = [task]
        return q

    def test_create_page_no_queue(self, qtbot) -> None:
        """不带 TaskQueue 创建 TaskPage，表格为空。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage()
        qtbot.addWidget(page)
        assert page.task_table.rowCount() == 0

    def test_create_page_with_queue(self, qtbot, mock_queue_with_tasks) -> None:
        """带 TaskQueue 创建 TaskPage，自动刷新显示任务。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage(mock_queue_with_tasks)
        qtbot.addWidget(page)
        assert page.task_table.rowCount() == 1

    def test_refresh_button(self, qtbot, mock_queue_with_tasks) -> None:
        """点击刷新按钮重新加载任务列表。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage(mock_queue_with_tasks)
        qtbot.addWidget(page)
        mock_queue_with_tasks.list_all.reset_mock()
        qtbot.mouseClick(page.btn_refresh, Qt.MouseButton.LeftButton)
        mock_queue_with_tasks.list_all.assert_called_once()

    def test_clear_completed(self, qtbot, mock_queue_with_tasks) -> None:
        """点击清除已完成按钮调用 queue.cancel 清理已完成任务。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage(mock_queue_with_tasks)
        qtbot.addWidget(page)
        mock_queue_with_tasks.cancel.reset_mock()
        qtbot.mouseClick(page.btn_clear, Qt.MouseButton.LeftButton)
        # 已完成/取消/失败的任务会被 cancel 标记清理
        assert mock_queue_with_tasks.cancel.call_count >= 1

    def test_table_columns(self, qtbot) -> None:
        """TaskPage 表格有 6 列并设置了正确的表头。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage()
        qtbot.addWidget(page)
        assert page.task_table.columnCount() == 6
        headers = [page.task_table.horizontalHeaderItem(i).text() for i in range(6)]  # type: ignore[union-attr]
        assert any("ID" in h or "id" in h.lower() for h in headers)
        assert any("类型" in h or "Type" in h for h in headers)

    def test_detail_view_readonly(self, qtbot) -> None:
        """详情文本框为只读。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage()
        qtbot.addWidget(page)
        assert page.detail_view.isReadOnly() is True
