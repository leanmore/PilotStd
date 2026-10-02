# 模块：项目/核心//脚本
"""通知消息数据类 + 渠道抽象基类（v1.1 起基类迁移至 channels.base）。

NotificationChannel 自 v1.1（Final-R2）起规范基类位于 channels.base：
本模块仅保留 NotificationMessage（全库引用），并对旧基类名做废弃转发
（访问时触发 DeprecationWarning，下个大版本再移除）。
"""

from __future__ import annotations

import warnings
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
    status: str = ""  # 单条状态标记：""（中性）/ "success" / "failure"（**业务结果态**，勿与投递态混用）
    target_id: str = ""  # 聚合分组子键（同 event_type 下按 target_id 分组）
    elapsed_ms: int = 0  # 单条耗时（毫秒），聚合时汇总为总耗时
    changed_at: str = ""  # 状态变更时间（ISO 格式），聚合消息中显示

    # ── 通知身份与生命周期（阶段 1a，2026-10-02）─────────────────────────────
    # 默认值即"现状语义"，故追加这些字段对既有 13 个字段与全部调用点零行为变更。
    # 设计背景见 docs/plans/notification-redesign/02-目标架构.md §2.2。
    message_id: str = ""  # 通知消息稳定 ID（uuid4().hex[:16]）；回调据此定位消息
    correlation_id: str = ""  # 同一次业务运行的关联键（同一批次的多条通知可归组）
    # 投递态：pending / sent / failed / suppressed / edited。
    # **刻意不复用 `status`**——后者是业务结果态（success/failure），两者语义不同。
    delivery_status: str = "pending"
    # 回执态：none / delivered / read / acted。渠道契约当前只有 send()->bool，故默认 none。
    ack_status: str = "none"


def __getattr__(name: str):
    """NotificationChannel 自 v1.1 起规范基类位于 channels.base，此处仅废弃转发。"""
    if name == "NotificationChannel":
        warnings.warn(
            "NotificationChannel is deprecated since v1.1; "
            "use pilotstd.core.notification.channels.base.NotificationChannel instead",
            DeprecationWarning,
            stacklevel=2,
        )
        # 惰性导入：避免与渠道基类模块（其导入本模块的通知消息类）循环依赖
        from .channels.base import NotificationChannel

        return NotificationChannel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
