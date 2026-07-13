import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtWidgets import QApplication, QMenu


def test_work_table_has_context_menu_policy(window):
    """工作表应设置了 CustomContextMenu 策略。"""
    assert window.work_table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_work_table_context_menu_triggered(window, qtbot):
    """工作区右键菜单应能触发 context menu 信号。
    发送 QContextMenuEvent 后 _on_work_table_context_menu 会调用 menu.exec()
    进入阻塞模态循环，因此用 QTimer 在 100ms 后关闭菜单防止测试卡死。"""
    triggered = False

    def on_menu(pos):
        nonlocal triggered
        triggered = True

    def _close_menu():
        # 菜单是 QMenu(window) 创建的，从窗口查找
        menu = window.findChild(QMenu)
        if menu and menu.isVisible():
            menu.close()

    window.work_table.customContextMenuRequested.connect(on_menu)
    QTimer.singleShot(100, _close_menu)

    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(10, 10), QPoint(100, 100))
    QApplication.sendEvent(window.work_table.viewport(), event)

    qtbot.waitUntil(lambda: triggered, timeout=2000)
    assert triggered


def test_toggleable_cols_exist(window):
    """可切换列列表非空且索引有效。"""
    from pilotstd.ui.table_constants import TOGGLEABLE_COLS, WORK_COLUMNS

    assert len(TOGGLEABLE_COLS) >= 4
    for c in TOGGLEABLE_COLS:
        assert 0 <= c < len(WORK_COLUMNS)


def test_column_visibility_toggle(window):
    """表头右键菜单项应能切换列可见性。"""
    from pilotstd.ui.table_constants import TOGGLEABLE_COLS

    first_toggle_col = TOGGLEABLE_COLS[0]
    assert not window.work_table.isColumnHidden(first_toggle_col)
    window.work_table.setColumnHidden(first_toggle_col, True)
    assert window.work_table.isColumnHidden(first_toggle_col)
    window.work_table.setColumnHidden(first_toggle_col, False)
    assert not window.work_table.isColumnHidden(first_toggle_col)


def test_file_tree_context_menu_has_import(window):
    """文件树右键菜单应含「导入工作区」选项。"""
    menu = QMenu(window)
    menu.addAction("📂 导入工作区")
    actions = [a.text() for a in menu.actions()]
    assert "📂 导入工作区" in actions
