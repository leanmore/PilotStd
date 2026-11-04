# 模块：项目/核心//____脚本
"""通知模块——多渠道消息分发。"""

import logging
import warnings
from typing import Any, Callable

from .channel import NotificationMessage
from .events import (
    EVENT_ARCHIVE_COMPLETE,
    EVENT_FIRST_REGISTERED,
    EVENT_STATUS_CHANGED,
)

logger = logging.getLogger(__name__)

# 系统级通知钩子：由容器层（docker/app.py）在启动时注入 NotificationManager 的 send_event。
# 供 core 内**拿不到 manager 引用**的模块（如公告熔断器）发系统通知，避免 core → docker 反向依赖。
_system_notifier: Callable[[str, dict[str, Any]], None] | None = None


def set_system_notifier(notifier: Callable[[str, dict[str, Any]], None] | None) -> None:
    """注入/清除系统通知钩子（容器启动时调用，测试可传 None 复位）。"""
    global _system_notifier
    _system_notifier = notifier


def notify_system(event_type: str, data: dict[str, Any]) -> None:
    """通过钩子发一条系统级通知；未注入钩子或发送失败时只记日志，不影响业务。"""
    if _system_notifier is None:
        return
    try:
        _system_notifier(event_type, data)
    except Exception as exc:  # noqa: BLE001 — 通知失败不得影响主流程，但必须留痕
        logger.warning("system notify failed: %s (%s)", event_type, exc)


__all__ = [
    "NotificationChannel",
    "NotificationMessage",
    "NotificationManager",
    "EVENT_ARCHIVE_COMPLETE",
    "EVENT_STATUS_CHANGED",
    "EVENT_EXPIRED",
    "EVENT_FIRST_REGISTERED",
    "set_system_notifier",
    "notify_system",
]


def __getattr__(name: str):
    """惰性导出：只在真正取用时才 import，避免"导入本包 = 拖入通知全栈"。

    - NotificationManager：门面类，其实现链会拖入构建器 / 渠道 / 凭证（全栈）；
      改为取用时再 import——2026-10-03 步 B D3 起，只取事件规格的消费方
      （如 `config.defaults`）不再被牵连加载全栈。**非废弃名，不告警**。
    - NotificationChannel：规范基类已迁移至 channels.base（v1.1 遗留名，访问即告警）
    - EVENT_EXPIRED：standard_expired 已合并入 standard_status_changed（is_expired 区分）
    """
    if name == "NotificationManager":
        from .manager import NotificationManager

        return NotificationManager
    if name == "NotificationChannel":
        warnings.warn(
            "NotificationChannel is deprecated since v1.1; "
            "use pilotstd.core.notification.channels.base.NotificationChannel instead",
            DeprecationWarning,
            stacklevel=2,
        )
        from .channels.base import NotificationChannel

        return NotificationChannel
    if name == "EVENT_EXPIRED":
        warnings.warn(
            "EVENT_EXPIRED is deprecated since v1.1; "
            "use standard_status_changed with is_expired=True instead",
            DeprecationWarning,
            stacklevel=2,
        )
        from .events import EVENT_EXPIRED

        return EVENT_EXPIRED
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
