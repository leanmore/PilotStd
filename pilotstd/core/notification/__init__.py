# 模块：项目/核心//____脚本
"""通知模块——多渠道消息分发。"""

import warnings

from .channel import NotificationMessage
from .events import (
    EVENT_ARCHIVE_COMPLETE,
    EVENT_FIRST_REGISTERED,
    EVENT_STATUS_CHANGED,
)
from .manager import NotificationManager

__all__ = [
    "NotificationChannel",
    "NotificationMessage",
    "NotificationManager",
    "EVENT_ARCHIVE_COMPLETE",
    "EVENT_STATUS_CHANGED",
    "EVENT_EXPIRED",
    "EVENT_FIRST_REGISTERED",
]


def __getattr__(name: str):
    """v1.1 遗留名惰性导出：访问时触发 DeprecationWarning（保护外部兼容，不删除）。

    - NotificationChannel：规范基类已迁移至 channels.base
    - EVENT_EXPIRED：standard_expired 已合并入 standard_status_changed（is_expired 区分）
    """
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
