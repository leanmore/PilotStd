# 模块：pilotstd/core/notify.py
# Windows Toast 通知服务 — 封装系统托盘 QSystemTrayIcon.showMessage()

import time
from typing import Any

from PyQt6.QtWidgets import QSystemTrayIcon


class NotifyService:
    """系统通知服务，提供跨模块的 Toast 通知入口。

    在 MainWindow._setup_tray() 中调用 NotifyService.init(tray) 初始化，
    之后各模块通过 NotifyService.get().show(...) 发送通知。

    内置去重：同标题通知 3 秒内不重复弹出，避免批量操作时通知轰炸。
    """

    _instance: "NotifyService | None" = None
    _DEDUP_WINDOW = 3.0  # 同标题去重窗口（秒）

    @classmethod
    def init(cls, tray: QSystemTrayIcon) -> None:
        cls._instance = cls(tray)

    @classmethod
    def get(cls) -> "NotifyService":
        """获取 NotifyService 单例，未初始化时静默降级。"""
        if cls._instance is None:
            cls._instance = cls(None)  # 未初始化时静默降级
        return cls._instance

    def __init__(self, tray: QSystemTrayIcon | None):
        self._tray = tray
        self._enabled = True
        self._last: dict[str, float] = {}  # title → last_emit_time

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    # ── 公共方法 ──

    def show(self, title: str, message: str, duration: int = 5000) -> None:
        """发送通知。经聚合器缓冲合并后显示。"""
        if not self._enabled or self._tray is None:
            return
        agg = self._get_aggregator()
        if not agg.auto_pause_enabled:
            if not self._check_dedup(title):
                return
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration)
            return
        agg.should_show(
            "info",
            title,
            message,
            lambda t, b, _l: self._tray.showMessage(  # type: ignore[arg-type]
                t, b, QSystemTrayIcon.MessageIcon.Information, duration
            ),
        )

    def show_warning(self, title: str, message: str, duration: int = 5000) -> None:
        """发送警告通知。经聚合器缓冲合并后显示。"""
        if not self._enabled or self._tray is None:
            return
        agg = self._get_aggregator()
        if not agg.auto_pause_enabled:
            if not self._check_dedup(title):
                return
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, duration)
            return
        agg.should_show(
            "warning",
            title,
            message,
            lambda t, b, _l: self._tray.showMessage(t, b, QSystemTrayIcon.MessageIcon.Warning, duration),
        )  # type: ignore[arg-type]

    # ── 内部 ──

    @staticmethod
    def _get_aggregator() -> Any:
        """惰性获取聚合器实例。"""
        from pilotstd.core.notification_aggregator import NotificationAggregator  # type: ignore[import-untyped]

        return NotificationAggregator()

    def _check_dedup(self, title: str) -> bool:
        """检查是否应发送。同标题在去重窗口内返回 False。"""
        now = time.monotonic()
        last = self._last.get(title, 0)
        if now - last < self._DEDUP_WINDOW:
            return False
        self._last[title] = now
        return True
