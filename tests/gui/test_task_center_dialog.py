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
        """创建 mock TaskQueue，返回示例任务列表。

        用**真实 `TaskInfo`** 而非 MagicMock：W1 的结果列会对计数做算术
        （`总数 - 成功 - 失败`），Mock 参与算术会直接抛 TypeError，且真实模型更贴近生产。
        """
        from pilotstd.task.models import TaskInfo, TaskStatus, TaskType

        task = TaskInfo(
            task_id="task-001",
            task_type=TaskType.QUERY,
            status=TaskStatus.COMPLETED,
            completed_items=5,
            total_items=5,
            failed_items=0,
            updated_at="2024-01-15T10:30:00.000000",
            error_log="",
        )

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
        """W1：点击"清除已完成"调用 queue.clear_finished（真删），不再复用 cancel。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage(mock_queue_with_tasks)
        qtbot.addWidget(page)
        mock_queue_with_tasks.clear_finished.reset_mock()
        mock_queue_with_tasks.cancel.reset_mock()
        qtbot.mouseClick(page.btn_clear, Qt.MouseButton.LeftButton)
        assert mock_queue_with_tasks.clear_finished.call_count == 1
        assert mock_queue_with_tasks.cancel.call_count == 0, "清除不是取消：不得再调用 cancel"

    def test_table_columns(self, qtbot) -> None:
        """W1：表格 5 列 = 业务 / 状态 / 结果 / 时间 / 提示（不再有任务ID与类型列）。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage()
        qtbot.addWidget(page)
        assert page.task_table.columnCount() == 5
        headers = [page.task_table.horizontalHeaderItem(i).text() for i in range(5)]  # type: ignore[union-attr]
        assert headers == ["业务", "状态", "结果", "时间", "提示"]
        assert not any("ID" in h for h in headers), "行单位是「一次用户操作」，不再展示任务ID"

    def test_row_renders_user_language(self, qtbot) -> None:
        """W1：一行 = 业务名 + 用户语言状态 + 结果摘要；失败行给出"需要我做什么"。"""
        from pilotstd.task.models import TaskInfo, TaskStatus, TaskType
        from pilotstd.ui.pages.task_page import TaskPage

        done = TaskInfo(
            task_id="t-done", task_type=TaskType.QUERY, status=TaskStatus.COMPLETED,
            total_items=10, completed_items=7, failed_items=1,
            updated_at="2026-01-15T10:30:00.000000",
        )
        failed = TaskInfo(
            task_id="t-fail", task_type=TaskType.DOWNLOAD, status=TaskStatus.FAILED,
            total_items=4, completed_items=1, failed_items=3,
            updated_at="2026-01-15T11:00:00.000000", error_log="连接超时",
        )
        running = TaskInfo(
            task_id="t-run", task_type=TaskType.SCAN, status=TaskStatus.RUNNING,
            total_items=20, completed_items=5, failed_items=0,
            updated_at="2026-01-15T11:05:00.000000",
        )
        q = MagicMock()
        q.list_all.return_value = [done, failed, running]
        page = TaskPage(q)
        qtbot.addWidget(page)

        def cell(row: int, col: int) -> str:
            return page.task_table.item(row, col).text()  # type: ignore[union-attr]

        assert cell(0, 0) == "查询"
        assert cell(0, 1) == "已完成"
        assert cell(0, 2) == "成功 7 / 失败 1 / 跳过 2"
        assert cell(0, 3) == "2026-01-15T10:30:00"
        assert cell(0, 4) == ""
        assert cell(1, 1) == "失败"
        assert cell(1, 2) == "成功 1 / 失败 3 / 跳过 0"
        assert cell(1, 4) == "看明细里的原因，必要时重试"
        assert cell(2, 0) == "扫描"
        assert cell(2, 1) == "进行中"
        assert cell(2, 2) == "5/20 (25%)", "进行中给进度，不给结果摘要"

    def test_selection_expands_detail(self, qtbot) -> None:
        """W1：选中行后明细可展开（错误原文不再挤在列表列里）。"""
        from pilotstd.task.models import TaskInfo, TaskStatus, TaskType
        from pilotstd.ui.pages.task_page import TaskPage

        failed = TaskInfo(
            task_id="t-fail", task_type=TaskType.DOWNLOAD, status=TaskStatus.FAILED,
            total_items=2, completed_items=0, failed_items=2,
            updated_at="2026-01-15T11:00:00.000000", error_log="连接超时",
            result_json='{"failed": 2}',
        )
        q = MagicMock()
        q.list_all.return_value = [failed]
        page = TaskPage(q)
        qtbot.addWidget(page)
        page.task_table.selectRow(0)
        text = page.detail_view.toPlainText()
        assert "下载" in text
        assert "错误明细：连接超时" in text
        assert "结果明细：" in text

    def test_detail_view_readonly(self, qtbot) -> None:
        """详情文本框为只读。"""
        from pilotstd.ui.pages.task_page import TaskPage

        page = TaskPage()
        qtbot.addWidget(page)
        assert page.detail_view.isReadOnly() is True
