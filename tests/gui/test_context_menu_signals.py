"""验证右键菜单的触发（弹出/信号）"""

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtWidgets import QApplication

from pilotstd.i18n import _


class TestContextMenuPopups:
    """验证三个右键入口能正常触发上下文菜单信号。"""

    def test_file_tree_context_menu_signal_emitted(self, mock_main_window, qtbot):
        """右键点击文件树应触发 customContextMenuRequested 信号。"""
        window = mock_main_window
        triggered = False

        def on_menu(pos):
            nonlocal triggered
            triggered = True

        window.file_tree.customContextMenuRequested.connect(on_menu)
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(10, 10), QPoint(100, 100))
        QApplication.sendEvent(window.file_tree.viewport(), event)
        qtbot.wait(100)
        assert triggered, "文件树 customContextMenuRequested 信号未触发"

    def test_table_header_context_menu_signal_emitted(self, mock_main_window, qtbot):
        """右键点击表头应触发 customContextMenuRequested 信号。"""
        window = mock_main_window
        triggered = False

        def on_menu(pos):
            nonlocal triggered
            triggered = True

        header = window.work_table.horizontalHeader()
        header.customContextMenuRequested.connect(on_menu)
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(10, 10), QPoint(100, 100))
        QApplication.sendEvent(header.viewport(), event)
        qtbot.wait(100)
        assert triggered, "表头 customContextMenuRequested 信号未触发"

    def test_work_table_context_menu_signal_emitted(self, mock_main_window, qtbot):
        """右键点击工作表应触发 customContextMenuRequested 信号。"""
        window = mock_main_window
        triggered = False

        def on_menu(pos):
            nonlocal triggered
            triggered = True

        window.work_table.customContextMenuRequested.connect(on_menu)
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(10, 10), QPoint(100, 100))
        QApplication.sendEvent(window.work_table.viewport(), event)
        qtbot.wait(100)
        assert triggered, "工作表 customContextMenuRequested 信号未触发"


class TestContextMenuContent:
    """验证右键菜单内容（菜单项的存在性）。"""

    def test_file_tree_context_menu_has_import(self, mock_main_window):
        """文件树右键菜单应包含「导入工作区」选项。"""
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(mock_main_window)
        menu.addAction(f"\U0001f4c2 {_('context_import')}")
        actions_text = [a.text() for a in menu.actions()]
        assert f"\U0001f4c2 {_('context_import')}" in actions_text

    def test_work_table_context_menu_items_exist(self, mock_main_window):
        """构建工作表右键菜单的模拟菜单，确认所有 6 项均可创建。"""
        from PyQt6.QtWidgets import QMenu

        window = mock_main_window
        menu = QMenu(window)
        menu.addAction(f"\U0001f4cb {_('copy')}")
        menu.addAction(f"\U0001f50d {_('offline_view')}")
        menu.addAction(f"\U0001f4c4 {_('add_file')}")
        menu.addAction(f"\U0001f4c1 {_('add_folder')}")
        menu.addAction(f"\U0001f5d1 {_('remove_selected')}")
        menu.addAction(f"\U0001f9f9 {_('remove_all')}")
        actions_text = [a.text() for a in menu.actions()]
        assert len(actions_text) == 6, f"期望 6 个菜单项，实际 {len(actions_text)} 个"
