# tests/gui/test_settings_dialog.py
# SettingsDialog 测试 — 设置对话框
# SettingsPage 内部依赖完整的 SettingsHandler/ConfigManager，
# 在单元测试中用真实 QWidget 子类替代以避免初始化整套 handler。

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QPushButton, QWidget


class MockSettingsPage(QWidget):
    """替代 SettingsPage 的 mock 控件，是真实 QWidget，可放入布局。"""

    def __init__(self, config_manager=None) -> None:
        super().__init__()
        self.save_to_config = MagicMock()


class TestSettingsDialog:
    """设置对话框测试。"""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """创建 mock ConfigManager。"""
        return MagicMock()

    @pytest.fixture
    def mock_page(self) -> MockSettingsPage:
        """创建 mock SettingsPage（真实 QWidget）。"""
        return MockSettingsPage()

    def test_create_dialog(self, qtbot, mock_config, mock_page) -> None:
        """对话框正常创建，标题和尺寸正确。"""
        with patch("pilotstd.ui.pages.settings._dialog.SettingsPage", return_value=mock_page):
            from pilotstd.ui.pages.settings._dialog import SettingsDialog

            dlg = SettingsDialog(mock_config)
            qtbot.addWidget(dlg)
            assert dlg.windowTitle() == "设置"
            assert dlg.width() >= 500

    def test_page_receives_config(self, qtbot, mock_config, mock_page) -> None:
        """SettingsPage 被传入 config_manager 参数。"""
        with patch("pilotstd.ui.pages.settings._dialog.SettingsPage", return_value=mock_page) as mock_sp:
            from pilotstd.ui.pages.settings._dialog import SettingsDialog

            dlg = SettingsDialog(mock_config)
            qtbot.addWidget(dlg)
            mock_sp.assert_called_once_with(mock_config)

    def test_accept_saves_and_shows_info(self, qtbot, mock_config, mock_page) -> None:
        """点击确定：调用 save_to_config + 弹出保存成功提示 + accept。"""
        with patch("pilotstd.ui.pages.settings._dialog.SettingsPage", return_value=mock_page):
            from pilotstd.ui.pages.settings._dialog import SettingsDialog

            dlg = SettingsDialog(mock_config)
            qtbot.addWidget(dlg)
            dlg.show()

            with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok) as mock_info:
                dlg._on_accept()
                mock_page.save_to_config.assert_called_once()
                mock_info.assert_called_once()
            assert dlg.result() == 1  # QDialog.Accepted

    def test_cancel_button_rejects(self, qtbot, mock_config, mock_page) -> None:
        """点击取消按钮触发 reject，不保存设置。"""
        with patch("pilotstd.ui.pages.settings._dialog.SettingsPage", return_value=mock_page):
            from pilotstd.ui.pages.settings._dialog import SettingsDialog

            dlg = SettingsDialog(mock_config)
            qtbot.addWidget(dlg)
            dlg.show()

            for btn in dlg.findChildren(QPushButton):
                if btn.text() == "取消":
                    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                    break
            assert dlg.result() == 0  # QDialog.Rejected

    def test_ok_button_triggers_accept(self, qtbot, mock_config, mock_page) -> None:
        """点击确定按钮触发 _on_accept 流程。"""
        with patch("pilotstd.ui.pages.settings._dialog.SettingsPage", return_value=mock_page):
            from pilotstd.ui.pages.settings._dialog import SettingsDialog

            dlg = SettingsDialog(mock_config)
            qtbot.addWidget(dlg)
            dlg.show()

            with patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok):
                for btn in dlg.findChildren(QPushButton):
                    if btn.text() == "确定":
                        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                        break
                mock_page.save_to_config.assert_called_once()
