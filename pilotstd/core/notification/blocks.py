# 模块：pilotstd/core/notification/blocks.py
"""通知消息的 Block 数据类——替代字符串拼接的结构化消息体。

每个 Block 代表消息中的一个语义单元（文本、键值对、状态变更、列表）。
消息构建器产出 Block 列表，渲染器将 Block 列表转为渠道特定格式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class NotificationBlock:
    """Block 基类——所有消息块的抽象父类，用于类型标注和分发。"""

    pass


@dataclass
class TextBlock(NotificationBlock):
    """纯文本块——最基础的语义单元，无额外格式。"""

    text: str


@dataclass
class KeyValueBlock(NotificationBlock):
    """键值对块——“字段名: 取值”样式的信息行。"""

    key: str
    value: str


@dataclass
class StatusChangeBlock(NotificationBlock):
    """状态变更块——用箭头直观表达"旧值 → 新值"的变迁。"""

    label: str
    old_value: str
    new_value: str


@dataclass
class ListBlock(NotificationBlock):
    """列表块——标题 + 条目集合的展示单元。

    items 中每个 dict 的典型键：
        number: 标准号 / 编号（渲染时加粗）
        name:   名称 / 描述
        status: 状态 / 其他补充信息

    total 为 None 时渲染 len(items)，非 None 时使用传入值。
    """

    title: str
    items: list[dict[str, str]] = field(default_factory=list)
    total: Optional[int] = None
    detail_url: Optional[str] = None
