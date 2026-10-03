# 模块：项目/核心//____脚本
"""通知模块——多渠道消息分发。"""

import warnings

from .channel import NotificationMessage
from .events import (
    EVENT_ARCHIVE_COMPLETE,
    EVENT_FIRST_REGISTERED,
    EVENT_STATUS_CHANGED,
)

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
