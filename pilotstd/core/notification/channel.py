# pilotstd/core/notification/channel.py
"""通知消息数据类 + 渠道抽象基类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class NotificationMessage:
    """统一通知消息结构。"""

    title: str
    body: str
    level: str = "info"  # info / warning / error
    standard_number: Optional[str] = None
    event_type: str = ""
    link: Optional[str] = None  # 跳转链接（如 /standards/GB/T 123-2024）
    icon: Optional[str] = None  # 图标标识（前端按类型渲染）
    aggregated_count: int = 1  # 聚合条数（1=未聚合，>1=合并了N条）


class NotificationChannel(ABC):
    """通知渠道抽象基类。"""

    @abstractmethod
    def send(self, message: NotificationMessage) -> bool:
        """发送通知，成功返回 True。"""
        ...

    @staticmethod
    def validate_config(config: dict) -> bool:
        """验证渠道配置是否完整。子类可覆盖。"""
        return True
