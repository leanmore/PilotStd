# 模块：项目/核心//____脚本
"""通知模块——多渠道消息分发。"""

from .channel import NotificationChannel, NotificationMessage
from .events import (
    EVENT_ARCHIVE_COMPLETE,
    EVENT_EXPIRED,
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
