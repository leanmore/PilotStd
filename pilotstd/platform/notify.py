# 模块：项目/核心/脚本
# 通知服务—封装系统托盘脚本()

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
    # 长阶段节流窗口（秒，W3）：**必须 > 桌面熔断的"30 秒内 3 条"**，
    # 否则进度类气泡会自己触发熔断暂停（5 分钟），正是分档策略要避免的
    LONG_STAGE_WINDOW = 60.0

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
        self._event_last: dict[str, float] = {}  # topic → last_emit_time（W3 长阶段节流）

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

    def show_event(self, title: str, message: str, level: str = "info", duration: int = 5000) -> None:
        """把**已分流到托盘**的业务事件弹成气泡，并遵守分档节流（W3）。

        分档规则（[02-framework-update.md](../../docs/plans/notification-system-design/02-framework-update.md) §三）：
        - **警告档**（`level` 为 `warning`/`error`）→ **立即发射**，不受节流（与 Docker 端
          "警告绕过聚合"同口径：失败/需人处置的事不能等窗口）；
        - 其余 → 同一**主题**在 `LONG_STAGE_WINDOW`（60 秒）内只弹一条。

        设计原文为"每 60 秒**或**每 25% 且间隔 ≥60 秒，取先到者"；**25% 检查点在本路径不适用**
        ——托盘事件只带标题/正文，没有进度百分比，故以时间为准（`Total/Completed` 类进度仍由
        应用内进度条承担）。节流只加在**本方法**：`show`/`show_warning`（既有 UI 直呼链路）
        行为逐字不变。
        """
        if level in ("warning", "error"):
            self.show_warning(title, message, duration)
            return
        topic = self._get_aggregator().topic_of(title, message)
        if not self._check_event_window(topic):
            return
        self.show(title, message, duration)

    # ── 内部 ──

    @staticmethod
    def _get_aggregator() -> Any:
        """惰性获取聚合器实例。"""
        from pilotstd.core.notification_aggregator import NotificationAggregator  # type: ignore[import-untyped]

        return NotificationAggregator()

    def _check_event_window(self, topic: str) -> bool:
        """长阶段节流：同主题在 `LONG_STAGE_WINDOW` 内只放行一次（返回 True 表示放行）。

        与 `_check_dedup`（3 秒同标题瞬时防抖）**不同层**：本方法按**主题**、窗口 60 秒，
        用于压住长阶段的重复进度；两者可以同时生效。
        """
        now = time.monotonic()
        last = self._event_last.get(topic, 0.0)
        if now - last < self.LONG_STAGE_WINDOW:
            return False
        self._event_last[topic] = now
        return True

    def _check_dedup(self, title: str) -> bool:
        """检查是否应发送。同标题在去重窗口内返回 False。

        职责边界（三套通知聚合/去重机制之一）：这是**3 秒同标题瞬时防抖**，
        目的是避免同一标题的托盘气泡瞬间重复弹出，与 `NotificationAggregator`
        的主题分组是**不同层次**的去重——前者按"标题字面相同 + 时间邻近"丢弃，
        后者按"主题相同"合并成一条摘要。

        注意两条路径**互斥**（见 `show`/`show_warning`）：本方法只在
        `auto_pause_enabled` 为 False（未启用自动暂停）时生效；启用自动暂停时
        走 `should_show()` → 服务端聚合器，由后者的 0.3 秒窗口完成合并去重，
        不再经过本方法。
        """
        now = time.monotonic()
        last = self._last.get(title, 0)
        if now - last < self._DEDUP_WINDOW:
            return False
        self._last[title] = now
        return True
