"""GUI 测试辅助函数 — 定位无 objectName 的菜单/托盘交互入口"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenu

from pilotstd.i18n import _


def find_action_by_text(menu: QMenu, key: str) -> Optional[QAction]:
    """在菜单中按翻译 key 匹配 action 的显示文本。"""
    expected_text = _(key)
    for action in menu.actions():
        if action.text() == expected_text:
            return action
    return None


def find_menu_by_text(window: QMainWindow, key: str) -> Optional[QMenu]:
    """在菜单栏中按翻译 key 匹配子菜单。"""
    expected_text = _(key)
    mb = window.menuBar()
    if mb is None:
        return None
    for action in mb.actions():
        if action.text() == expected_text:
            return action.menu()
    return None


def get_tray_menu(window: QMainWindow) -> Optional[QMenu]:
    """获取系统托盘上下文菜单。"""
    if hasattr(window, "_tray") and window._tray is not None:
        return window._tray.contextMenu()
    return None


def trigger_menu_action(window: QMainWindow, menu_key: str, action_key: str) -> QAction:
    """按翻译 key 定位菜单项并触发（模拟点击）。返回触发的 QAction。"""
    menu = find_menu_by_text(window, menu_key)
    assert menu is not None, f"菜单 '{menu_key}' (显示为 '{_(menu_key)}') 未找到"
    action = find_action_by_text(menu, action_key)
    assert action is not None, f"菜单项 '{action_key}' (显示为 '{_(action_key)}') 未找到"
    action.trigger()
    return action
