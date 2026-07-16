# tests/gui/test_welcome_dialog.py
# WelcomeDialog 测试 — 首次启动欢迎对话框
# 注意：WelcomeDialog 构造函数有双重 super().__init__() 调用，
# 在 pytest-qt 环境下 qtbot.addWidget 会导致 session cleanup 挂起，
# 因此本测试使用 qapp fixture 而非 qtbot，手动管理控件生命周期。

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox


class TestWelcomeDialog:
    """首次启动欢迎对话框测试。"""

    def test_create_dialog(self, qapp) -> None:
        """对话框正常创建，标题和尺寸正确。"""
        from pilotstd.ui.welcome_dialog import WelcomeDialog

        dlg = WelcomeDialog()
        try:
            assert dlg.windowTitle() == "欢迎"
            assert dlg.isModal() is True
            assert dlg.width() >= 400
        finally:
            dlg.deleteLater()

    def test_skip_checkbox_default_unchecked(self, qapp) -> None:
        """skip 复选框默认为未勾选。"""
        from pilotstd.ui.welcome_dialog import WelcomeDialog

        dlg = WelcomeDialog()
        try:
            assert dlg.should_skip() is False
        finally:
            dlg.deleteLater()

    def test_skip_checkbox_checked(self, qapp) -> None:
        """勾选 skip 复选框后 should_skip 返回 True。"""
        from pilotstd.ui.welcome_dialog import WelcomeDialog

        dlg = WelcomeDialog()
        try:
            dlg.skip_cb.setChecked(True)
            assert dlg.should_skip() is True
        finally:
            dlg.deleteLater()

    def test_label_contains_welcome_html(self, qapp) -> None:
        """QLabel 包含富文本欢迎内容。"""
        from pilotstd.ui.welcome_dialog import WelcomeDialog

        dlg = WelcomeDialog()
        try:
            assert dlg.label.textFormat() == Qt.TextFormat.RichText
            assert "PilotStd" in dlg.label.text()
        finally:
            dlg.deleteLater()

    def test_should_skip_persists_after_accept(self, qapp) -> None:
        """accept 后 should_skip 状态仍可读取。"""
        from pilotstd.ui.welcome_dialog import WelcomeDialog

        dlg = WelcomeDialog()
        try:
            dlg.skip_cb.setChecked(True)
            dlg.accept()
            assert dlg.should_skip() is True
        finally:
            dlg.deleteLater()

    def test_welcome_text_static_content(self) -> None:
        """WELCOME_TEXT 常量包含关键引导词。"""
        from pilotstd.ui.welcome_dialog import WELCOME_TEXT

        assert "PilotStd" in WELCOME_TEXT
        assert "标准" in WELCOME_TEXT
        assert "扫描" in WELCOME_TEXT or "scan" in WELCOME_TEXT.lower()
