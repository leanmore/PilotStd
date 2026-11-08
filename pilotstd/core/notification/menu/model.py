"""菜单模型 + 校验（不绑渠道）。

所有渠道共用同一套 MenuItem/Menu；渠道差异只放在 `channel_limits()`：
- wechat：3 个顶级，每个最多 5 个二级；支持 view/click/group
- feishu：3 个顶级，每个最多 5 个二级；支持 view/group（群菜单 redirect）
- telegram：3 个命令（命令列表，不是持久菜单）；支持 command
- dingtalk：官方机器人无持久菜单；保留 0 上限用于“明确不支持”
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 渠道闭集；新增渠道必须同时补 clients/limits/tests
CHANNELS = ("wechat", "feishu", "telegram", "dingtalk")
# 菜单项类型闭集（group 只用于二级分组的父项）
SUPPORTED_TYPES = frozenset({"view", "click", "command", "group"})
MAX_TOP = 3
MAX_CHILDREN = 5
_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class MenuValidationError(ValueError):
    """菜单配置不合法。"""


@dataclass(frozen=True)
class MenuItem:
    """一个菜单项；`url`/`command`/`key` 按 type 取用。"""

    id: str
    label_key: str
    type: str
    order: int = 1
    url: str = ""
    command: str = ""
    key: str = ""
    children: tuple["MenuItem", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Menu:
    """一个渠道的完整菜单。"""

    channel: str
    items: tuple[MenuItem, ...] = field(default_factory=tuple)
    enabled: bool = True


def channel_limits(channel: str) -> tuple[int, int, frozenset[str]]:
    """返回 `(顶级上限, 每个顶级的二级上限, 支持的 type)`。"""
    # 企微/飞书支持二级分组；Telegram 只支持扁平命令；钉钉无持久菜单
    if channel == "wechat":
        return 3, 5, frozenset({"view", "click", "group"})
    if channel == "feishu":
        return 3, 5, frozenset({"view", "group"})
    if channel == "telegram":
        return 3, 0, frozenset({"command"})
    if channel == "dingtalk":
        return 0, 0, frozenset()
    raise MenuValidationError(f"unknown channel: {channel}")


def _check_url(value: str, field_name: str) -> None:
    """URL 只允许站内相对路径或 http(s)，拒绝脚本/内联协议。"""
    value = value.strip()
    if not value:
        raise MenuValidationError(f"{field_name} must not be empty")
    lowered = value.lower()
    if lowered.startswith(("javascript:", "data:")):
        raise MenuValidationError(f"{field_name} must not use javascript:/data:")
    if not (value.startswith("/") or lowered.startswith(("http://", "https://"))):
        raise MenuValidationError(f"{field_name} must be a site-relative path or http(s) URL")


def _check_item(item: MenuItem, allowed: frozenset[str], children_limit: int) -> None:
    """逐项校验；children 只允许一层。"""
    if not _ID_RE.match(item.id):
        raise MenuValidationError(f"invalid menu id: {item.id!r}")
    if not item.label_key.strip():
        raise MenuValidationError(f"{item.id}: label_key is required")
    if item.type not in allowed:
        raise MenuValidationError(f"{item.id}: type {item.type!r} not supported")
    if item.type == "group":
        if not item.children:
            raise MenuValidationError(f"{item.id}: group menu requires children")
    if item.type == "view":
        _check_url(item.url, f"{item.id}.url")
        if item.children:
            raise MenuValidationError(f"{item.id}: view menu cannot have children")
    if item.type == "click":
        if not item.key.strip():
            raise MenuValidationError(f"{item.id}: click menu requires key")
        if item.children:
            raise MenuValidationError(f"{item.id}: click menu cannot have children")
    if item.type == "command":
        cmd = item.command.strip()
        if not re.match(r"^/[a-zA-Z0-9_]{1,32}$", cmd):
            raise MenuValidationError(f"{item.id}: command must look like /cmd (1-32 chars)")
    if len(item.children) > children_limit:
        raise MenuValidationError(f"{item.id}: too many children (>{children_limit})")
    for child in item.children:
        _check_item(child, allowed, 0)


def validate(menu: Menu) -> None:
    """校验渠道、项数、id 唯一、order 连续、type 合法、url 安全。"""
    top_limit, child_limit, allowed = channel_limits(menu.channel)
    # 停用且为空是合法状态（用于“先关菜单，稍后再配”）
    if not menu.enabled and not menu.items:
        return
    if len(menu.items) > top_limit:
        raise MenuValidationError(f"{menu.channel}: too many top-level items (>{top_limit})")
    if not menu.items:
        raise MenuValidationError(f"{menu.channel}: at least one menu item is required")
    ids: set[str] = set()
    orders: list[int] = []
    for item in menu.items:
        if item.id in ids:
            raise MenuValidationError(f"duplicate menu id: {item.id}")
        ids.add(item.id)
        orders.append(item.order)
        _check_item(item, allowed, child_limit)
        for child in item.children:
            if child.id in ids:
                raise MenuValidationError(f"duplicate menu id: {child.id}")
            ids.add(child.id)
    if sorted(orders) != list(range(1, len(orders) + 1)):
        raise MenuValidationError("top-level order must start at 1 and be contiguous")


# 同步快照：固定字段顺序，保证 last_synced 比较稳定
def menu_to_dict(menu: Menu) -> dict:
    """稳定结构（用于配置 diff / 测试断言）。"""
    return {
        "channel": menu.channel,
        "enabled": menu.enabled,
        "items": [_item_to_dict(item) for item in menu.items],
    }


def _item_to_dict(item: MenuItem) -> dict:
    """递归转 dict；字段顺序固定，便于 last_synced 比较。"""
    return {
        "id": item.id,
        "label_key": item.label_key,
        "type": item.type,
        "order": item.order,
        "url": item.url,
        "command": item.command,
        "key": item.key,
        "children": [_item_to_dict(child) for child in item.children],
    }
