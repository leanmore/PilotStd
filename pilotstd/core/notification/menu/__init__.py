"""通知渠道菜单的渠道无关模型与校验。"""

from .clients import (
    DingtalkMenuClient,
    FeishuMenuClient,
    MenuClient,
    MenuResult,
    TelegramCommandClient,
    WecomMenuClient,
)
from .model import Menu, MenuItem, MenuValidationError, channel_limits

__all__ = [
    "DingtalkMenuClient",
    "FeishuMenuClient",
    "Menu",
    "MenuClient",
    "MenuItem",
    "MenuResult",
    "MenuValidationError",
    "TelegramCommandClient",
    "WecomMenuClient",
    "channel_limits",
]
