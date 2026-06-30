# pilotstd/ui/pages/settings/_core.py
# SettingsPage 核心类 — 组合所有设置 Tab mixin，管理导航与布局

from typing import Any

from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget, QWidget

from ._appearance import _AppearanceTab
from ._columns import _ColumnsTab
from ._compat import _CompatTab
from ._config_load import _ConfigLoadTab
from ._config_save import _ConfigSaveTab
from ._network import _NetworkTab
from ._notification import _NotificationTab
from ._ocr import _OcrTab
from ._scan import _ScanTab
from ._storage import _StorageTab


class SettingsPage(
    _StorageTab,
    _NetworkTab,
    _AppearanceTab,
    _ScanTab,
    _CompatTab,
    _NotificationTab,
    _OcrTab,
    _ColumnsTab,
    _ConfigLoadTab,
    _ConfigSaveTab,
    QWidget,
):
    """设置表单，左侧导航列表 + 右侧 QStackedWidget。"""

    def __init__(self, config_manager: Any = None) -> None:
        super().__init__()
        self._config = config_manager

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

        self._build_storage_page()
        self._build_network_page()
        self._build_ui_page()
        self._build_scan_page()
        self._build_compat_page()
        self._build_notification_page()
        self._build_ocr_page()
        self._build_columns_page()

        main_layout.addWidget(self._nav)
        main_layout.addWidget(self._stack, 1)

        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)

        if self._config:
            self._load_from_config()

    # ── 辅助：添加页面到导航和堆叠 ──

    def _add_page(self, name: str, widget: QWidget) -> None:
        item = QListWidgetItem(name)
        self._nav.addItem(item)
        self._stack.addWidget(widget)
