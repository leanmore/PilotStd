# tests/gui/test_dialogs.py
# ConfigPageDialog + ExportFileListDialog 测试

from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class TestConfigPageDialog:
    """通用配置页面对话框测试。"""

    def test_create_with_widget(self, qtbot) -> None:
        """用任意 QWidget 创建对话框，标题和子控件正确。"""
        from pilotstd.ui.dialogs import ConfigPageDialog

        page = QLabel("测试页面")
        dlg = ConfigPageDialog(page, "测试标题")
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "测试标题"
        assert dlg.width() >= 500

    def test_close_button_accepts(self, qtbot) -> None:
        """点击关闭按钮触发 accept。"""
        from pilotstd.ui.dialogs import ConfigPageDialog

        page = QLabel("测试页面")
        dlg = ConfigPageDialog(page, "测试标题")
        qtbot.addWidget(dlg)
        dlg.show()

        # 找到关闭按钮并点击
        from PyQt6.QtWidgets import QPushButton

        for btn in dlg.findChildren(QPushButton):
            if btn.text() == "关闭":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break
        assert dlg.result() == 1  # QDialog.Accepted

    def test_different_title(self, qtbot) -> None:
        """不同标题参数正确设置窗口标题。"""
        from pilotstd.ui.dialogs import ConfigPageDialog

        dlg = ConfigPageDialog(QLabel("内容"), "高级设置")
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "高级设置"

    def test_layout_contains_page_widget(self, qtbot) -> None:
        """布局中包含传入的页面控件。"""
        from pilotstd.ui.dialogs import ConfigPageDialog

        page = QLabel("自定义内容")
        dlg = ConfigPageDialog(page, "标题")
        qtbot.addWidget(dlg)
        # 页面控件应该是布局的第一个子项
        layout = dlg.layout()
        assert layout.itemAt(0).widget() is page


class TestExportFileListDialog:
    """导出文件清单对话框测试。"""

    def test_create_dialog(self, qtbot) -> None:
        """对话框正常创建，source_path 和 include_path 默认值正确。"""
        from pilotstd.ui.dialogs import ExportFileListDialog

        dlg = ExportFileListDialog(None, "D:/test/path")
        qtbot.addWidget(dlg)
        assert dlg.source_path == "D:/test/path"
        assert dlg.include_path is False
        assert dlg.windowTitle() == "导出文件列表"

    def test_include_checkbox_toggle(self, qtbot) -> None:
        """勾选包含路径复选框。"""
        from pilotstd.ui.dialogs import ExportFileListDialog

        dlg = ExportFileListDialog(None, "D:/test/path")
        qtbot.addWidget(dlg)
        dlg.include_cb.setChecked(True)
        dlg._on_accept()
        assert dlg.include_path is True

    def test_include_checkbox_unchecked(self, qtbot) -> None:
        """不勾选包含路径复选框，include_path 保持 False。"""
        from pilotstd.ui.dialogs import ExportFileListDialog

        dlg = ExportFileListDialog(None, "D:/test/path")
        qtbot.addWidget(dlg)
        dlg._on_accept()
        assert dlg.include_path is False

    def test_cancel_button_rejects(self, qtbot) -> None:
        """点击取消按钮触发 reject。"""
        from PyQt6.QtWidgets import QPushButton

        from pilotstd.ui.dialogs import ExportFileListDialog

        dlg = ExportFileListDialog(None, "D:/test/path")
        qtbot.addWidget(dlg)
        dlg.show()

        for btn in dlg.findChildren(QPushButton):
            if btn.text() == "取消":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break
        assert dlg.result() == 0  # QDialog.Rejected

    def test_ok_button_sets_include_path_and_accepts(self, qtbot) -> None:
        """点击确定按钮设置 include_path 并 accept。"""
        from PyQt6.QtWidgets import QPushButton

        from pilotstd.ui.dialogs import ExportFileListDialog

        dlg = ExportFileListDialog(None, "D:/test/path")
        qtbot.addWidget(dlg)
        dlg.include_cb.setChecked(True)
        dlg.show()

        for btn in dlg.findChildren(QPushButton):
            if btn.text() == "确定":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break
        assert dlg.result() == 1
        assert dlg.include_path is True

    def test_change_folder_mock(self, qtbot) -> None:
        """模拟更改文件夹——选择新路径后 source_path 更新。"""
        from pilotstd.ui.dialogs import ExportFileListDialog

        dlg = ExportFileListDialog(None, "D:/old/path")
        qtbot.addWidget(dlg)

        with patch("pilotstd.ui.dialogs.QFileDialog.getExistingDirectory", return_value="D:/new/path"):
            dlg._change_folder()

        assert dlg.source_path == "D:/new/path"

    def test_change_folder_cancelled(self, qtbot) -> None:
        """取消文件夹选择时 source_path 不变。"""
        from pilotstd.ui.dialogs import ExportFileListDialog

        dlg = ExportFileListDialog(None, "D:/old/path")
        qtbot.addWidget(dlg)
        original = dlg.source_path

        with patch("pilotstd.ui.dialogs.QFileDialog.getExistingDirectory", return_value=""):
            dlg._change_folder()

        assert dlg.source_path == original
