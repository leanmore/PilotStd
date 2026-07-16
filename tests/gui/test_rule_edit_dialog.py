# tests/gui/test_rule_edit_dialog.py
# RuleEditDialog 测试 — 网站规则编辑对话框

from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QPushButton


class TestRuleEditDialog:
    """网站规则编辑对话框测试。"""

    def test_create_empty_rule(self, qtbot) -> None:
        """不带已有规则创建对话框，所有字段为空。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "编辑网站规则"
        assert dlg.name_edit.text() == ""
        assert dlg.url_edit.text() == ""
        assert dlg.xpath_edit.text() == ""
        assert dlg.regex_edit.text() == ""

    def test_create_with_existing_rule(self, qtbot) -> None:
        """带已有规则创建对话框，字段预填充。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        rule = {
            "name": "工标网",
            "type": "查询",
            "url": "https://www.csres.com/s.jsp?keyword=%s",
            "xpath": "//div[@class='result']",
            "regex": r"\d+",
            "captcha": "digit",
        }
        dlg = RuleEditDialog(None, rule)
        qtbot.addWidget(dlg)
        assert dlg.name_edit.text() == "工标网"
        assert dlg.url_edit.text() == "https://www.csres.com/s.jsp?keyword=%s"
        assert dlg.xpath_edit.text() == "//div[@class='result']"
        assert dlg.regex_edit.text() == r"\d+"

    def test_accept_empty_name_shows_warning(self, qtbot) -> None:
        """名称为空时点击确定弹出警告，不关闭对话框。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)
        dlg.name_edit.clear()

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok) as mock_warn:
            dlg._on_accept()
            mock_warn.assert_called_once()

    def test_accept_valid_name(self, qtbot) -> None:
        """填入有效名称点击确定，对话框 accept。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)
        dlg.name_edit.setText("测试规则")
        dlg.show()

        dlg._on_accept()
        assert dlg.result() == 1  # QDialog.Accepted

    def test_get_rule_returns_filled_dict(self, qtbot) -> None:
        """get_rule 返回填写内容的字典。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)
        dlg.name_edit.setText("新规则")
        dlg.url_edit.setText("https://example.com/search?q=%s")
        dlg.xpath_edit.setText("//div")
        dlg.regex_edit.setText(r".*")
        dlg.type_combo.setCurrentText("下载")

        rule = dlg.get_rule()
        assert rule["name"] == "新规则"
        assert rule["type"] == "下载"
        assert rule["url"] == "https://example.com/search?q=%s"
        assert rule["xpath"] == "//div"
        assert rule["regex"] == r".*"

    def test_get_rule_defaults(self, qtbot) -> None:
        """空规则 get_rule 返回默认值（空字符串）。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)

        rule = dlg.get_rule()
        assert rule["name"] == ""
        assert rule["captcha"] == ""

    def test_cancel_button_rejects(self, qtbot) -> None:
        """点击取消按钮触发 reject。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)
        dlg.show()

        for btn in dlg.findChildren(QPushButton):
            if btn.text() == "取消":
                qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
                break
        assert dlg.result() == 0  # QDialog.Rejected

    def test_captcha_combo_default_none(self, qtbot) -> None:
        """验证码下拉框默认选中'无'。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)
        assert dlg.captcha_combo.currentIndex() == 0

    def test_captcha_combo_mapping(self, qtbot) -> None:
        """验证码下拉框选项与 get_rule 映射一致。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)
        dlg.name_edit.setText("测试")

        # 选择算术验证码（index 2 → "math"）
        dlg.captcha_combo.setCurrentIndex(2)
        rule = dlg.get_rule()
        assert rule["captcha"] == "math"

        # 选择滑动验证码（index 3 → "slide"）
        dlg.captcha_combo.setCurrentIndex(3)
        rule = dlg.get_rule()
        assert rule["captcha"] == "slide"

    def test_type_combo_default_and_switch(self, qtbot) -> None:
        """类型下拉框默认'查询'，可切换到'下载'。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        dlg = RuleEditDialog(None)
        qtbot.addWidget(dlg)

        # 默认选中第一项
        assert dlg.type_combo.currentText() in ("查询", "Query")
        dlg.type_combo.setCurrentIndex(1)
        assert dlg.type_combo.currentText() in ("下载", "Download")

    def test_partial_rule_fills_only_existing(self, qtbot) -> None:
        """部分字段有值的规则，只填充已有字段。"""
        from pilotstd.ui.pages.rules_page import RuleEditDialog

        rule = {"name": "仅名称"}
        dlg = RuleEditDialog(None, rule)
        qtbot.addWidget(dlg)
        assert dlg.name_edit.text() == "仅名称"
        assert dlg.url_edit.text() == ""
