# pilotstd/ui/qt_lifecycle.py
"""Qt 对象生命周期工具 —— 处理"窗口已销毁、后台信号迟到"的竞态。

背景：跨线程信号走**队列投递**，`disconnect()` 只能阻止**之后**的发射，
已经排进主线程事件队列的调用仍会被执行。取消/关闭窗口时若只置停止标志，
槽函数会在控件析构后运行并抛
`RuntimeError: wrapped C/C++ object of type X has been deleted`。

本模块提供两个原语：
- `is_qt_alive()`：判断 Qt 包装对象的 C++ 实体是否仍在；
- `stop_worker_gracefully()`：先断连接再协作式停止线程（严禁 `terminate()`）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

# 超时未退出的线程在此保活。
# QThread 在运行中被析构会让 Qt 直接终止进程
# （"QThread: Destroyed while thread is still running"），
# 因此宁可留引用等它自然结束，也不用 terminate() 强杀。
_ORPHANED_WORKERS: list[Any] = []


def _sip_isdeleted() -> Any:
    """取回 sip.isdeleted；PyQt6 里 sip 是 PyQt6 的子模块（顶层 import sip 不存在）。"""
    try:
        from PyQt6 import sip as _sip
    except ImportError:  # pragma: no cover - 仅在无 PyQt6 的环境触发
        return None
    return getattr(_sip, "isdeleted", None)


def is_qt_alive(obj: Any) -> bool:
    """判断对象是否仍可用（非 None 且底层 C++ 实体未被析构）。

    非 Qt 对象（普通 Python 对象、Mock）视为存活：调用方只关心"能不能安全访问"。
    """
    if obj is None:
        return False
    isdeleted = _sip_isdeleted()
    if isdeleted is None:  # pragma: no cover - 防御性分支
        return True
    try:
        return not bool(isdeleted(obj))
    except (TypeError, RuntimeError):
        # TypeError: 不是 sip 包装对象；RuntimeError: 包装对象已失效
        return True


def _forget_orphan(worker: Any) -> None:
    """线程自然结束后释放保活引用。"""
    try:
        _ORPHANED_WORKERS.remove(worker)
    except ValueError:
        pass


def _keep_alive_until_finished(worker: Any) -> None:
    """把仍在运行的线程挂到模块级保活列表，并脱离即将销毁的父对象。"""
    if worker in _ORPHANED_WORKERS:
        return
    _ORPHANED_WORKERS.append(worker)
    try:
        worker.setParent(None)  # 否则父窗口析构时会连带杀掉运行中的线程
        worker.finished.connect(lambda: _forget_orphan(worker))
    except (AttributeError, RuntimeError):
        _forget_orphan(worker)
        return
    if not worker.isRunning():  # 建立连接期间线程已结束 → 立即释放
        _forget_orphan(worker)


def stop_worker_gracefully(worker: Any, signals: Iterable[Any] = (), timeout_ms: int = 5000) -> bool:
    """协作式停止后台线程：先断信号，再置停止标志，最后等待退出。

    顺序不可颠倒：队列里已排队的信号调用不会被 disconnect 撤销，
    但先断开能保证从此刻起不再有新的槽调用去触碰即将析构的控件。

    严禁 `QThread.terminate()`：强杀可能让线程在持锁或写文件时中断，
    造成数据损坏与析构期崩溃。超时未退出时转为保活等待自然结束。

    Args:
        worker: QThread 实例（None 视为已停止）。
        signals: 需要断开的业务信号（不含 QThread 内建 started/finished）。
        timeout_ms: 等待线程退出的毫秒数。

    Returns:
        True 表示线程已确认退出（或本就没在运行）。
    """
    if worker is None:
        return True

    for sig in signals:
        try:
            sig.disconnect()
        except (TypeError, RuntimeError):
            pass  # 未连接或底层对象已析构，无需处理

    stop = getattr(worker, "stop", None)
    if callable(stop):
        stop()

    try:
        worker.requestInterruption()
        if not worker.isRunning():
            return True
        if worker.wait(timeout_ms):
            return True
    except RuntimeError:
        return True  # C++ 对象已析构，视作已停止

    logger.warning(
        "Worker %s 未在 %dms 内退出，已保活等待其自然结束（不使用 terminate）",
        type(worker).__name__,
        timeout_ms,
    )
    _keep_alive_until_finished(worker)
    return False
