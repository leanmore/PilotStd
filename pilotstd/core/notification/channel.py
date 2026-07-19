# pilotstd/core/notification/channel.py
"""通知消息数据类 + 渠道抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .blocks import NotificationBlock


@dataclass
class NotificationMessage:
    """统一通知消息结构。"""

    title: str
    blocks: list[NotificationBlock] = field(default_factory=list)
    body: str = ""  # 向后兼容：blocks 为空时回退渲染 body
    level: str = "info"  # info / warning / error
    standard_number: str | None = None
    event_type: str = ""
    link: str | None = None  # 跳转链接（如 /standards/GB/T 123-2024）
    icon: str | None = None  # 图标标识（前端按类型渲染）
    aggregated_count: int = 1  # 聚合条数（1=未聚合，>1=合并了N条）
    status: str = ""  # 单条状态标记：""（中性）/ "success" / "failure"
    target_id: str = ""  # 聚合分组子键（同 event_type 下按 target_id 分组）
    elapsed_ms: int = 0  # 单条耗时（毫秒），聚合时汇总为总耗时
    changed_at: str = ""  # 状态变更时间（ISO 格式），聚合消息中显示


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
