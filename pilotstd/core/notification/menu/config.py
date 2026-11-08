"""菜单配置解析：`notification.menus.<channel>` → Menu。"""

from __future__ import annotations

from typing import Any

from .model import Menu, MenuItem, validate


def _parse_item(raw: dict[str, Any]) -> MenuItem:
    """递归解析一个菜单项（children 只允许一层，由 validate 兜底）。"""
    children = tuple(_parse_item(c) for c in (raw.get("children") or []))
    return MenuItem(
        id=str(raw.get("id") or ""),
        label_key=str(raw.get("label_key") or ""),
        type=str(raw.get("type") or ""),
        order=int(raw.get("order") or 1),
        url=str(raw.get("url") or ""),
        command=str(raw.get("command") or ""),
        key=str(raw.get("key") or ""),
        children=children,
    )


def menu_from_config(channel: str, raw: dict[str, Any] | None) -> Menu:
    """把 config 字典解析成 Menu 并校验。"""
    data = raw or {}
    menu = Menu(
        channel=channel,
        items=tuple(_parse_item(item) for item in (data.get("items") or [])),
        enabled=bool(data.get("enabled", True)),
    )
    validate(menu)
    return menu


def load_menu(channel: str, cfg: Any) -> Menu:
    """从 ConfigManager 读取并校验。"""
    raw = cfg.get(f"notification.menus.{channel}") or {}
    return menu_from_config(channel, raw)
