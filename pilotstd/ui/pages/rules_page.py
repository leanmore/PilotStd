# pilotstd/ui/pages/rules_page.py
# 网站规则配置：管理查询/下载网站的适配规则模板

import json
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QLabel,
    QDialog, QMessageBox, QHeaderView,
    QFileDialog,
)

from ...i18n import _


class RulesPage(QWidget):
    """网站规则配置控件：展示已保存的规则列表。"""

    def __init__(self, config_manager=None):
        super().__init__()
        self._config = config_manager
        layout = QVBoxLayout(self)

        # 规则列表
        rule_group = QGroupBox(_("rule_group"))
        rule_layout = QHBoxLayout(rule_group)
        self.rule_tree = QTreeWidget()
        self.rule_tree.setHeaderLabels([_("header_rule_name"), _("header_task_type"), _("header_url")])
        self.rule_tree.setColumnWidth(0, 120)
        self.rule_tree.setColumnWidth(1, 60)
        self.rule_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.rule_tree.itemDoubleClicked.connect(self._on_edit_rule)
        btn_layout = QVBoxLayout()
        btn_add = QPushButton(_("btn_add"))
        btn_add.clicked.connect(self._on_add_rule)
        btn_edit = QPushButton(_("btn_edit"))
        btn_edit.clicked.connect(self._on_edit_rule)
        btn_del = QPushButton(_("btn_delete"))
        btn_del.clicked.connect(self._on_delete_rule)
        btn_copy = QPushButton(_("btn_copy_builtin"))
        btn_copy.clicked.connect(self._on_copy_builtin)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_copy)
        btn_layout.addStretch()
        btn_import = QPushButton(_("btn_import_json"))
        btn_import.clicked.connect(self._on_import_json)
        btn_layout.addWidget(btn_import)
        btn_export = QPushButton(_("btn_export_json"))
        btn_export.clicked.connect(self._on_export_json)
        btn_layout.addWidget(btn_export)
        rule_layout.addWidget(self.rule_tree)
        rule_layout.addLayout(btn_layout)
        layout.addWidget(rule_group)

        if self._config:
            self._refresh()

    def _get_rules(self) -> list[dict]:
        raw = self._config.get("sites.rules", "[]")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return []
        # ConfigManager 可能将 JSON 数组反序列化为 Python list
        if isinstance(raw, list):
            return raw
        return []
        return raw

    def _save_rules(self, rules: list[dict]):
        self._config.set("sites.rules", json.dumps(rules, ensure_ascii=False))
        self._config.save()

    def _refresh(self):
        self.rule_tree.clear()
        for r in self._get_rules():
            self._add_item(r)

    def _add_item(self, rule: dict):
        item = QTreeWidgetItem([rule.get("name", ""), rule.get("type", ""), rule.get("url", "")])
        item.setData(0, 1, rule)
        self.rule_tree.addTopLevelItem(item)

    def _on_add_rule(self):
        dlg = RuleEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            rules = self._get_rules()
            rules.append(dlg.get_rule())
            self._save_rules(rules)
            self._refresh()

    def _on_edit_rule(self, item=None):
        if item is None:
            items = self.rule_tree.selectedItems()
            if not items:
                return
            item = items[0]
        if isinstance(item, QTreeWidgetItem):
            rule = item.data(0, 1)
            dlg = RuleEditDialog(self, rule)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                rules = self._get_rules()
                idx = next(i for i, r in enumerate(rules) if r.get("name") == rule.get("name"))
                rules[idx] = dlg.get_rule()
                self._save_rules(rules)
                self._refresh()

    def _on_delete_rule(self):
        items = self.rule_tree.selectedItems()
        if not items:
            return
        rule = items[0].data(0, 1)
        confirm = QMessageBox.question(self, _("title_confirm_delete"), _("confirm_delete_rule").format(name=rule.get('name')))
        if confirm == QMessageBox.StandardButton.Yes:
            rules = self._get_rules()
            rules = [r for r in rules if r.get("name") != rule.get("name")]
            self._save_rules(rules)
            self._refresh()

    def _on_import_json(self):
        path, __ = QFileDialog.getOpenFileName(self, _("dialog_import_rules"), "",
                                                _("file_filter_json"))
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            QMessageBox.warning(self, _("title_import_failed"), _("msg_import_read_error").format(error=e))
            return

        imported = data.get("rules", []) if isinstance(data, dict) else data
        if not isinstance(imported, list):
            QMessageBox.warning(self, _("title_format_error"),
                                _("msg_invalid_json_format"))
            return

        rules = self._get_rules()
        added = 0
        for rule in imported:
            if not isinstance(rule, dict) or "name" not in rule:
                continue
            if not any(r.get("name") == rule["name"] for r in rules):
                rules.append({
                    "name": rule.get("name", ""),
                    "type": rule.get("type", _("rule_type_query")),
                    "url": rule.get("url", ""),
                    "xpath": rule.get("xpath", ""),
                    "regex": rule.get("regex", ""),
                    "captcha": rule.get("captcha", ""),
                })
                added += 1

        self._save_rules(rules)
        self._refresh()
        QMessageBox.information(self, _("title_import_done"), _("msg_import_success").format(count=added))

    def _on_export_json(self):
        rules = self._get_rules()
        if not rules:
            QMessageBox.information(self, _("title_hint"), _("msg_no_rules_to_export"))
            return
        path, __ = QFileDialog.getSaveFileName(self, _("dialog_export_rules"), "pilotstd_rules.json",
                                                _("file_filter_json"))
        if not path:
            return
        payload = {
            "version": "1.0",
            "description": _("msg_export_description"),
            "rules": rules,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, _("title_export_done"),
                                    _("msg_export_success").format(count=len(rules), path=path))
        except OSError as e:
            QMessageBox.warning(self, _("title_export_failed"), str(e))

    def _on_copy_builtin(self):
        builtins = [
            {"name": "工标网", "type": "查询", "url": "https://www.csres.com/s.jsp?keyword=%s"},
            {"name": "南京标准网", "type": "查询", "url": "https://www.njbz365.cn/"},
            {"name": "全国标准信息公共服务平台(G)", "type": "查询", "url": "https://openstd.samr.gov.cn/bzgk/std/std_list?p.p1=0&p.p2=%s"},
            {"name": "openstd 下载", "type": "下载", "url": "https://openstd.samr.gov.cn/bzgk/gb/showGb?type=online&hcno=%s"},
        ]
        rules = self._get_rules()
        for b in builtins:
            if not any(r.get("name") == b["name"] for r in rules):
                rules.append(b)
        self._save_rules(rules)
        self._refresh()


class RuleEditDialog(QDialog):
    """网站规则编辑对话框。"""

    def __init__(self, parent, rule: dict = None):
        super().__init__(parent)
        self.setWindowTitle(_("title_edit_rule"))
        self.resize(450, 350)
        self._rule = rule or {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(self._rule.get("name", ""))
        self.name_edit.setPlaceholderText(_("placeholder_rule_name"))
        form.addRow(_("label_rule_name"), self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems([_("rule_type_query"), _("rule_type_download")])
        if self._rule.get("type"):
            self.type_combo.setCurrentText(self._rule["type"])
        form.addRow(_("label_type"), self.type_combo)

        self.url_edit = QLineEdit(self._rule.get("url", ""))
        self.url_edit.setPlaceholderText(_("placeholder_url"))
        form.addRow(_("label_url"), self.url_edit)

        self.xpath_edit = QLineEdit(self._rule.get("xpath", ""))
        self.xpath_edit.setPlaceholderText(_("placeholder_xpath"))
        form.addRow("XPATH:", self.xpath_edit)

        self.regex_edit = QLineEdit(self._rule.get("regex", ""))
        self.regex_edit.setPlaceholderText(_("placeholder_regex"))
        form.addRow(_("label_regex"), self.regex_edit)

        self.captcha_combo = QComboBox()
        self.captcha_combo.addItems([_("captcha_none"), _("captcha_alphanumeric"), _("captcha_arithmetic"), _("captcha_slide"), _("captcha_click")])
        captcha_map = {"": 0, "digit": 1, "math": 2, "slide": 3, "click": 4}
        self.captcha_combo.setCurrentIndex(captcha_map.get(self._rule.get("captcha", ""), 0))
        form.addRow(_("label_captcha_type"), self.captcha_combo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton(_("btn_ok"))
        btn_ok.clicked.connect(self._on_accept)
        btn_layout.addWidget(btn_ok)
        btn_cancel = QPushButton(_("btn_cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, _("title_hint"), _("msg_enter_rule_name"))
            return
        self.accept()

    def get_rule(self) -> dict:
        captcha_map = {0: "", 1: "digit", 2: "math", 3: "slide", 4: "click"}
        return {
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentText(),
            "url": self.url_edit.text().strip(),
            "xpath": self.xpath_edit.text().strip(),
            "regex": self.regex_edit.text().strip(),
            "captcha": captcha_map.get(self.captcha_combo.currentIndex(), ""),
        }
