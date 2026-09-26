# tests/gui/helpers/__init__.py
"""GUI 测试辅助工具。"""

from __future__ import annotations

import logging
from typing import Optional

import pytestqt.qtbot
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenu

from pilotstd.i18n import _

from .predicates import thread_finished, worker_done, worker_finished

logger = logging.getLogger(__name__)

# 对话框处理器——供测试模块通过 from tests.gui.helpers import ... 引用
from .dialog_handler import (  # noqa: F401, E402
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

#: 真实 MainWindow 把 worker 挂在各 UI handler 上（窗口本身**没有** `_*_worker` 属性）。
#: 旧实现 `getattr(window, worker_attr, None)` 因此恒取到 None → 静默跳过线程等待 →
#: 53 处 `wait_for_worker_and_ui` 全部退化成空操作，掩盖了 CI 上的 QThread 生命周期崩溃。
_WORKER_HANDLERS = ("scan", "query", "download", "archive", "announce", "auto")


def resolve_worker(window, worker):
    """把 worker 规格解析为真实对象；**找不到就断言失败**，绝不静默跳过。

    Args:
        window: 窗口对象（真实 MainWindow，或测试里的假窗口）
        worker: 三种写法之一
            - worker 对象本身（直接返回）
            - 窗口上的属性名（如 "_test_worker"，假窗口场景）
            - handler 上的属性名（如 "_scan_worker"、" _query_worker"，真实窗口场景）
            - 点分路径（如 "_core.query._query_worker"，显式指定，调试用）

    Raises:
        AssertionError: 属性路径不存在（写错名字/结构变了），或解析结果为 None（worker 未创建）。
    """
    if not isinstance(worker, str):
        assert worker is not None, "wait_for_worker_and_ui: worker 对象为 None"
        return worker

    if "." in worker:
        obj = window
        walked = "window"
        for part in worker.split("."):
            assert hasattr(obj, part), (
                f"wait_for_worker_and_ui: 路径 '{worker}' 不存在——{walked} 上没有 '{part}'"
            )
            obj = getattr(obj, part)
            walked = f"{walked}.{part}"
        assert obj is not None, f"wait_for_worker_and_ui: 路径 '{worker}' 解析为 None（worker 尚未创建）"
        return obj

    if hasattr(window, worker):
        found = getattr(window, worker)
    else:
        found = _MISSING = object()
        core = getattr(window, "_core", None)
        for name in _WORKER_HANDLERS:
            handler = getattr(core, name, None) if core is not None else None
            if handler is not None and hasattr(handler, worker):
                found = getattr(handler, worker)
                break
        assert found is not _MISSING, (
            f"wait_for_worker_and_ui: 找不到 worker '{worker}'——窗口与 "
            f"_core.{{{','.join(_WORKER_HANDLERS)}}} 上都没有该属性（写错了？结构变了？）"
        )
    assert found is not None, (
        f"wait_for_worker_and_ui: worker '{worker}' 为 None（尚未创建）——"
        f"请确认等待前确实启动了对应操作"
    )
    return found


def wait_for_worker_and_ui(
    qtbot: pytestqt.qtbot.QtBot,
    window,
    worker_attr,
    ui_predicate=None,
    timeout: int = 5000,
    message: Optional[str] = None,
):
    """等待 Worker 线程结束 + UI 状态收敛的原子操作。

    Args:
        qtbot: pytest-qt bot 实例
        window: 窗口对象
        worker_attr: worker 对象 / 属性名 / 点分路径（见 `resolve_worker`）
        ui_predicate: UI 就绪条件（必须幂等、无副作用）；传 `worker_done` 哨兵或 None
                      时表示"只等 worker 结束"
        timeout: 最大等待时间（毫秒）
        message: 超时时的自定义错误信息；若不提供则自动生成
    """
    worker = resolve_worker(window, worker_attr)
    worker_name = worker_attr if isinstance(worker_attr, str) else repr(worker_attr)

    # L1: 等待 Worker 线程**真正**结束（isFinished 为准，覆盖"已 start 未 run"窗口）
    try:
        qtbot.waitUntil(lambda: thread_finished(worker), timeout=timeout)
    except Exception:
        raise AssertionError(f"Worker '{worker_name}' did not finish within {timeout}ms")

    # L2: 等待 UI 状态收敛；worker_done/None 等价于"worker 已结束"（L1 已保证）
    if ui_predicate is None or ui_predicate is worker_done:
        ui_predicate = worker_finished(worker)

    if message is None:
        message = f"Worker '{worker_name}' finished but UI condition not met within {timeout}ms"

    try:
        qtbot.waitUntil(ui_predicate, timeout=timeout)
    except Exception:
        raise AssertionError(message)
