# tests/gui/helpers/__init__.py
"""GUI 测试辅助工具。"""

from __future__ import annotations

import logging
import warnings
from typing import Callable, Optional

import pytestqt.qtbot
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenu

from pilotstd.i18n import _

logger = logging.getLogger(__name__)

# 对话框处理器——供测试模块通过 from tests.gui.helpers import ... 引用
from .dialog_handler import (  # noqa: F401
    PYWAUTO_AVAILABLE,
    PYWAUTO_ERROR,
    FileDialogAutoHandler,
    SmartDialogInterceptor,
    get_qfiledialog_patches,
    get_qmessagebox_patches,
)


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


# ════════════════════════════════════════════════════════════════
# Worker + UI 等待原子操作
# ════════════════════════════════════════════════════════════════


def wait_for_worker_and_ui(
    qtbot: pytestqt.qtbot.QtBot,
    window,
    worker_attr: str,
    ui_predicate: Callable[[], bool],
    timeout: int = 5000,
    message: Optional[str] = None,
):
    """等待 Worker 线程结束 + UI 状态收敛的原子操作。

    Args:
        qtbot: pytest-qt bot 实例
        window: 窗口对象（包含 worker 属性）
        worker_attr: worker 属性名，如 "_normalize_worker"
        ui_predicate: UI 就绪条件（必须幂等、无副作用），
                      如 lambda: table.rowCount() > 0
        timeout: 最大等待时间（毫秒）
        message: 超时时的自定义错误信息；若不提供则自动生成
    """
    worker = getattr(window, worker_attr, None)

    # L1: 等待 Worker 线程结束
    if worker is not None and worker.isRunning():
        try:
            qtbot.waitUntil(
                lambda: not worker.isRunning(),
                timeout=timeout,
            )
        except Exception:
            raise AssertionError(
                f"Worker '{worker_attr}' did not finish within {timeout}ms"
            )
    elif worker is None:
        logger.debug(
            "wait_for_worker_and_ui: worker '%s' is None, skipping thread wait",
            worker_attr,
        )

    # L2: 等待 UI 状态收敛
    if message is None:
        if worker is None:
            message = (
                f"Worker '{worker_attr}' does not exist and UI condition "
                f"not met within {timeout}ms"
            )
        else:
            message = (
                f"Worker '{worker_attr}' finished but UI condition "
                f"not met within {timeout}ms"
            )

    try:
        qtbot.waitUntil(ui_predicate, timeout=timeout)
    except Exception:
        raise AssertionError(message)


def _wait_worker(qtbot, window, worker_attr, timeout=5000):
    """Deprecated: 请使用 :func:`wait_for_worker_and_ui` 代替。

    此函数仅等待 Worker 线程结束，不保证 UI 状态收敛，
    在跨线程信号回调场景下会导致测试不稳定。
    """
    warnings.warn(
        "_wait_worker is deprecated. Use wait_for_worker_and_ui instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    worker = getattr(window, worker_attr, None)
    if worker is not None and worker.isRunning():
        qtbot.waitUntil(
            lambda: not worker.isRunning(),
            timeout=timeout,
        )
