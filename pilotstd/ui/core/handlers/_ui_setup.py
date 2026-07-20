# pilotstd/ui/core/handlers/_ui_setup.py
"""UISetupHandler — UI 构建（系统托盘、日志桥接、自动保存、扫描器状态管理）。

菜单栏/工具栏已提取至 _ui_toolbar.py，中央区域布局已提取至 _ui_layout.py。
"""

from __future__ import annotations

import atexit
import logging
import signal
from typing import Any, Callable, Optional

from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)

from ....i18n import _
from ...workers import LogHandler
from ._ui_layout import _UISetupLayoutMixin
from ._ui_toolbar import _UISetupToolbarMixin

logger = logging.getLogger("pilotstd.ui")


class UISetupHandler(_UISetupToolbarMixin, _UISetupLayoutMixin):
    """UI 构建 — 提供所有 setup_* 方法。

    通过依赖注入替代多重继承，window 作为方法参数传入以访问 MainWindow 的回调。
    菜单栏/工具栏由 _UISetupToolbarMixin 提供，中央区域布局由 _UISetupLayoutMixin 提供。
    """

    def __init__(
        self,
        config: Any,
        mgr: Any,
        project: Any,
        status_callback: Callable[[str], None],
        progress_callback: Callable[[int], None],
        on_auto_save: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._mgr = mgr
        self._project = project
        self._status = status_callback
        self._progress = progress_callback
        self._on_auto_save = on_auto_save
        self._parent = parent

    # ================================================================
    # 系统托盘
    # ================================================================

    def setup_tray(self, window: QWidget) -> QSystemTrayIcon:
        """系统托盘：最小化到托盘，双击恢复。返回 tray 实例供后续使用。"""
        tray = QSystemTrayIcon(window)
        tray.setIcon(window.windowIcon())
        tray.setToolTip("PilotStd")
        tray_menu = QMenu()
        tray_menu.addAction(_("tray_show"), window._restore_from_tray)
        tray_menu.addSeparator()
        tray_menu.addAction(_("exit"), window._quit_app)
        tray.setContextMenu(tray_menu)
        tray.activated.connect(window._on_tray_activated)
        tray.show()
        from ....platform.notify import NotifyService

        NotifyService.init(tray)
        return tray

    def on_tray_activated(self, reason: object, window: QWidget) -> None:
        """托盘图标激活回调。"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            window._restore_from_tray()

    # ================================================================
    # 日志 + 扫描器
    # ================================================================

    def setup_log_handler(self, log_view: QWidget) -> LogHandler:
        """设置日志处理器。"""
        handler = LogHandler(log_view)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
        return handler

    def setup_scanner(self) -> dict[str, Any]:
        """初始化扫描器状态，返回状态字典。"""
        return {
            "parsed_results": [],
            "unrecognized_files": [],
            "scan_source_root": "",
        }

    # ================================================================
    # 自动保存
    # ================================================================

    def setup_auto_save(self, window: QWidget) -> None:
        """连接自动保存信号。"""
        app = QApplication.instance()
        assert app is not None, "QApplication 未初始化"
        app.aboutToQuit.connect(self._on_auto_save)
        app.aboutToQuit.connect(window._on_shutdown_aggregator)
        atexit.register(window._on_atexit_save)
        try:
            signal.signal(signal.SIGTERM, lambda *a: self._on_auto_save())
        except (ValueError, OSError):
            pass

    def on_shutdown_aggregator(self) -> None:
        """退出前刷新聚合器中残留的通知消息（防止丢失）。"""
        try:
            from pilotstd.core.notification_aggregator import NotificationAggregator

            NotificationAggregator().shutdown()
        except Exception:
            pass

    # ================================================================
    # 工具方法
    # ================================================================

    def set_toolbar_enabled(self, toolbar_buttons: dict[str, Any], enabled: bool) -> None:
        """统一控制工具栏按钮状态。"""
        keys = (
            "btn_select",
            "btn_query",
            "btn_download",
            "btn_normalize",
            "btn_save",
            "btn_auto",
            "btn_announce",
            "btn_pause",
        )
        for key in keys:
            btn = toolbar_buttons.get(key)
            if btn is not None:
                btn.setEnabled(enabled)

    def get_library_root(self) -> str:
        """获取库根目录。"""
        from ....core.config import get_library_root

        return get_library_root(self._config)
