# 模块：项目//核心/_脚本
"""EventBus — 单例事件总线，替代跨 Handler 回调链。

特性：
- 单例模式，全局唯一实例
- QMutex 跨线程安全
- QMetaObject.invokeMethod + QueuedConnection 确保回调在主线程执行
- 支持 weakref 订阅，自动清理已销毁的订阅者
- reset() 静止协议（R2）：退役实例 + 排空已排队 deliver + deleteLater 延迟销毁，
  切断 teardown 期间“销毁 QObject／其它线程仍在 publish”的跨线程内存访问窗口
"""

from __future__ import annotations

import logging
import weakref
from typing import Any, Callable

from PyQt6.QtCore import (
    Q_ARG,
    QCoreApplication,
    QMetaObject,
    QMutex,
    QMutexLocker,
    QObject,
    Qt,
    QThread,
    pyqtSlot,
)

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
    # 静止协议门闸（类级）：reset() 期间为 True——此刻任何 publish 都无副作用直接返回
    _resetting = False

    def __init__(self) -> None:
        super().__init__()
        self._subscribers: dict[str, list[Callable[..., Any]]] = {}
        self._weak_subscribers: dict[str, list[weakref.ref[Any]]] = {}
        # 静止协议门闸（实例级）：reset() 退役本实例后置 False——
        # 此后任何**经旧引用**（其它线程早先持有的 bus 变量）的 publish/subscribe 都变成 no-op，
        # 不会再去触碰这个正在销毁的 QObject。
        self._accepting = True

    @classmethod
    def instance(cls) -> EventBus:
        """获取全局单例（线程安全）。"""
        with QMutexLocker(cls._lock):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试隔离）。

        **静止协议（R2，2026-09-27 第十二轮 R12-4）**——原实现在此处同步销毁 QObject
        （`cls._instance = None`），而其它线程可能仍在 `publish()` 或已排队的 `deliver` 中引用它
        → Windows 原生层 use-after-free（CI `test-gui-unit` 三次 access violation 的根因）。
        现改为四步：

        ① **关门**：置类级 `_resetting`、实例级 `_accepting=False` 并摘除订阅者——
           此后任何线程的 `publish()` 都是 no-op（不入队、不抛异常）；
        ② **有界排空**：仅当实例属于本线程时直接处理一次事件队列，把此前排队的 deliver 跑完；
           **不再使用无界的 `BlockingQueuedConnection`**——实测（R12-4 冒烟测试）当实例的线程
           亲和性落在没有事件循环的线程时，无界阻塞会把 teardown 永久挂住；跨线程残留的
           deliver 由 ① 的 `_accepting` 门闸在 `deliver()` 里丢弃，安全性不依赖排空；
        ③ **延迟销毁**：`deleteLater()` 交给事件循环，**绝不在此刻同步析构** QObject；
        ④ **复位**：清 `_resetting`，下一次 `instance()` 创建全新实例。
        """
        with QMutexLocker(cls._lock):
            instance = cls._instance
            cls._resetting = True  # ① 关门（先于任何清理，杜绝新入队）
            if instance is None:
                cls._resetting = False
                return
            instance._accepting = False
            instance._subscribers.clear()
            instance._weak_subscribers.clear()
            # 先摘掉单例引用：新调用 instance() 会拿到全新实例，而不是这个退役对象
            cls._instance = None

        try:
            # ② 有界排空（绝不无界阻塞）
            if instance.thread() is QThread.currentThread():
                app = QCoreApplication.instance()
                if app is not None:
                    app.processEvents()
        except RuntimeError:
            # 实例可能已被 GC 或 QApplication 未就绪，安全忽略
            pass
        finally:
            # ③ 延迟销毁：把 QObject 的析构挪到事件循环，避免与在途线程的跨线程访问交错
            try:
                instance.deleteLater()
            except RuntimeError:
                pass
            with QMutexLocker(cls._lock):
                cls._resetting = False  # ④ 复位，允许后续 publish 正常入队

    # ── 订阅管理 ─────────────────────────────────────────────

    def subscribe(
        self, event: str, callback: Callable[..., Any], weak: bool = True
    ) -> None:
        """订阅事件。weak=True 时使用弱引用，订阅者销毁后自动清理。

        静止协议（R2）：reset() 窗口内或实例已退役时直接返回——避免向正在销毁的
        对象写入新的订阅状态（那同样是 teardown 期的跨线程状态访问）。

        Args:
            event: 事件名（如 "scan.finished"）
            callback: 回调函数
            weak: 是否使用弱引用（默认 True）
        """
        if EventBus._resetting or not self._accepting:
            return
        with QMutexLocker(self._lock):
            if EventBus._resetting or not self._accepting:
                return
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)
            if weak:
                if event not in self._weak_subscribers:
                    self._weak_subscribers[event] = []
                ref = self._get_callback_ref(callback)
                if ref is not None:
                    self._weak_subscribers[event].append(ref)

    def unsubscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """取消订阅（静止协议同 subscribe：退役实例上的调用为 no-op）。"""
        if EventBus._resetting or not self._accepting:
            return
        with QMutexLocker(self._lock):
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(callback)
                except ValueError:
                    pass

    # ── 事件发布 ─────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> None:
        """发布事件（线程安全，回调在主线程执行）。

        **静止协议（R2）**：reset() 窗口内（类级 `_resetting`）或经已退役实例
        （实例级 `_accepting=False`）调用时**无副作用直接返回**——不入队、不抛异常，
        从源头切断“销毁 QObject 的同时其它线程还在往它身上投递”的跨线程访问。

        Args:
            event: 事件名
            data: 事件数据
        """
        if EventBus._resetting or not self._accepting:
            return
        with QMutexLocker(self._lock):
            # 锁内二次确认：与 reset() 的临界区互斥，保证“入队”与“退役”不交错；
            # 且入队动作本身也在临界区内 → reset() 拿到锁即意味着没有 in-flight publish 正在入队。
            if EventBus._resetting or not self._accepting:
                return
            callbacks = list(self._subscribers.get(event, []))
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
        if not self._accepting:
            # 已退役实例：即便有排队的 deliver 漏网，这里也直接丢弃（不再触碰订阅者状态）
            return
        with QMutexLocker(self._lock):
            callbacks = list(self._subscribers.get(event, []))
        for cb in callbacks:
            try:
                cb(data)
            except Exception:
                logger.exception("EventBus 回调异常: event=%s", event)

    # ── 同步屏障槽函数 ────────────────────────────────────────

    @pyqtSlot()
    def _drain_barrier(self) -> None:
        """空槽函数，仅用作 BlockingQueuedConnection 的同步屏障。

        Qt 事件队列 FIFO 保证：当此槽被执行时，之前所有
        QueuedConnection 的 deliver 调用必定已经完成。
        """

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
        if event in self._subscribers:
            self._subscribers[event] = [
                c for c in self._subscribers[event] if self._is_callback_alive(c)
            ]
        if not self._subscribers.get(event):
            self._subscribers.pop(event, None)
            self._weak_subscribers.pop(event, None)

    def _is_callback_alive(self, callback: Callable[..., Any]) -> bool:
        """检查回调绑定的对象是否仍然存活。"""
        try:
            if hasattr(callback, "__self__"):
                return callback.__self__ is not None
            return True  # 普通函数/静态方法始终存活
        except Exception:
            return False
