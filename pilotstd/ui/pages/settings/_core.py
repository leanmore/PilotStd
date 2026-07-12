# pilotstd/ui/pages/settings/_core.py
"""SettingsPage — 设置页面，组合 SettingsHandler 管理导航与布局。"""

from typing import Any

from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget, QWidget

from ...core.handlers._settings import SettingsHandler


class SettingsPage(QWidget):
    """设置表单，左侧导航列表 + 右侧 QStackedWidget。"""

    def __init__(self, config_manager: Any = None) -> None:
        super().__init__()
        self._config = config_manager
        self._handler = SettingsHandler(config_manager, parent=self)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 左侧导航 ──
        self._nav = QListWidget()
        self._nav.setFixedWidth(120)
        self._nav.setSpacing(0)
        self._nav.setStyleSheet("QListWidget { border: none; border-right: 1px solid #ddd; }")

        # ── 右侧堆叠 ──
        self._stack = QStackedWidget()
        self._handler.build_all_pages(self._stack)

        # ── 从 handler 获取页面名称填充导航 ──
        for name in self._handler.page_names:
            item = QListWidgetItem(name)
            self._nav.addItem(item)

        main_layout.addWidget(self._nav)
        main_layout.addWidget(self._stack, 1)

        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)

        if self._config:
            self._handler.load_all_configs()

    def save_to_config(self) -> None:
        """委托 handler 保存所有设置，保留原公开 API 签名。"""
        self._handler.save_all_configs()
