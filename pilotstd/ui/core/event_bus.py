# 模块：项目//核心/_脚本
"""EventBus — 单例事件总线，替代跨 Handler 回调链。

特性：
- 单例模式，全局唯一实例
- QMutex 跨线程安全
- QMetaObject.invokeMethod + QueuedConnection 确保回调在主线程执行
- 支持 weakref 订阅，自动清理已销毁的订阅者
"""

from __future__ import annotations

import logging
import weakref
from typing import Any, Callable

from PyQt6.QtCore import Q_ARG, QMetaObject, QMutex, QMutexLocker, QObject, Qt, pyqtSlot

logger = logging.getLogger(__name__)


class EventBus(QObject):
    """单例事件总线。

    用法:
        bus = EventBus.instance()
        bus.subscribe("scan.finished", my_handler)
        bus.publish("scan.finished", {"count": 5})
        bus.unsubscribe("scan.finished", my_handler)
    """

    _instance: EventBus | None = None
    _lock = QMutex()

    def __init__(self) -> None:
        super().__init__()
        self._subscribers: dict[str, list[Callable[..., Any]]] = {}
        # 存储引用追踪，用于清理
        self._weak_subscribers: dict[str, list[weakref.ref[Any]]] = {}

    @classmethod
    def instance(cls) -> EventBus:
        """获取全局单例（线程安全）。"""
        with QMutexLocker(cls._lock):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试隔离）。"""
        with QMutexLocker(cls._lock):
            if cls._instance is not None:
                cls._instance._subscribers.clear()
                cls._instance._weak_subscribers.clear()
            cls._instance = None

    # ── 订阅管理 ─────────────────────────────────────────────

    def subscribe(self, event: str, callback: Callable[..., Any], weak: bool = True) -> None:
        """订阅事件。weak=True 时使用弱引用，订阅者销毁后自动清理。

        Args:
            event: 事件名（如 "scan.finished"）
            callback: 回调函数
            weak: 是否使用弱引用（默认 True）
        """
        with QMutexLocker(self._lock):
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)
            if weak:
                if event not in self._weak_subscribers:
                    self._weak_subscribers[event] = []
                # 尝试从回调中提取弱引用（绑定的方法）
                ref = self._get_callback_ref(callback)
                if ref is not None:
                    self._weak_subscribers[event].append(ref)

    def unsubscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """取消订阅。"""
        with QMutexLocker(self._lock):
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(callback)
                except ValueError:
                    pass

    # ── 事件发布 ─────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> None:
        """发布事件（线程安全，回调在主线程执行）。

        Args:
            event: 事件名
            data: 事件数据
        """
        with QMutexLocker(self._lock):
            callbacks = list(self._subscribers.get(event, []))
            # 清理已死的弱引用
            self._clean_dead_refs(event)
        if callbacks:
            QMetaObject.invokeMethod(
                self,
                "deliver",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, event),
                Q_ARG(object, data),
            )

    @pyqtSlot(str, object)
    def deliver(self, event: str, data: Any) -> None:
        """在主线程中执行回调（由 QMetaObject.invokeMethod 调用）。"""
        with QMutexLocker(self._lock):
            callbacks = list(self._subscribers.get(event, []))
        for cb in callbacks:
            try:
                cb(data)
            except Exception:
                logger.exception("EventBus 回调异常: event=%s", event)

    # ── 内部辅助 ─────────────────────────────────────────────

    @staticmethod
    def _get_callback_ref(callback: Callable[..., Any]) -> weakref.ref[Any] | None:
        """从回调中提取弱引用。"""
        try:
            if hasattr(callback, "__self__"):
                return weakref.ref(callback.__self__)
            return None
        except Exception:
            return None

    def _clean_dead_refs(self, event: str) -> None:
        """清理已死亡的回调引用。"""
        if event not in self._weak_subscribers:
            return
        alive = []
        for ref in self._weak_subscribers[event]:
            obj = ref()
            if obj is not None:
                alive.append(ref)
        self._weak_subscribers[event] = alive
        # 清理对应的强引用列表
        if event in self._subscribers:
            self._subscribers[event] = [c for c in self._subscribers[event] if self._is_callback_alive(c)]
        if not self._subscribers.get(event):
            self._subscribers.pop(event, None)
            self._weak_subscribers.pop(event, None)

    def _is_callback_alive(self, callback: Callable[..., Any]) -> bool:
        """检查回调绑定的对象是否仍然存活。"""
        try:
            if hasattr(callback, "__self__"):
                return True  # 绑定方法, __self__ 存在即存活
            return True  # 普通函数/静态方法始终存活
        except Exception:
            return False
