# 模块：项目//核心/_脚本
"""EventBus — 单例事件总线，替代跨 Handler 回调链。

特性：
- 单例模式，全局唯一实例
- threading.Lock 跨线程安全（R12-8：原 QMutex/QMutexLocker 在「线程反复创建/销毁」下会触发
  PyQt6/sip 弱引用记账竞态 → 原生访问违例，见 docs/technical-debt.md 7.21/7.22）
- QMetaObject.invokeMethod + QueuedConnection 确保回调在主线程执行
- 支持 weakref 订阅，自动清理已销毁的订阅者
- reset() **保活单例**（R12-5）：只清空订阅者状态与递增世代号，**永不销毁 QObject**——
  从根上消除「析构 × 其它线程仍持有引用」的 use-after-free 窗口（R4 探针实测 0xC0000005 的根因）
"""

from __future__ import annotations

import logging
import threading
import weakref
from typing import Any, Callable

from PyQt6.QtCore import (
    Q_ARG,
    QCoreApplication,
    QMetaObject,
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
    # R12-8：改用 CPython 原生锁——临界区全是纯 Python 操作，无需 Qt 锁；
    # 原 QMutex/QMutexLocker 在多线程反复创建/销毁的场景下会崩溃（PyWeakref_NewRef(NULL)）。
    _lock = threading.Lock()
    # 静止协议门闸（类级）：reset() 期间为 True——此刻任何 publish 都无副作用直接返回
    _resetting = False

    def __init__(self) -> None:
        super().__init__()
        self._subscribers: dict[str, list[Callable[..., Any]]] = {}
        self._weak_subscribers: dict[str, list[weakref.ref[Any]]] = {}
        # 世代号：reset() 每次 +1。publish 时把当前世代号随事件入队，deliver 时丢弃陈旧世代
        # ——这样「reset 前排队的 deliver」不会误触 reset 之后新注册的回调（状态隔离不依赖销毁对象）。
        self._generation = 0

    @classmethod
    def instance(cls) -> EventBus:
        """获取全局单例（线程安全）。"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例**状态**（仅用于测试隔离）——**实例保活，永不析构**。

        **保活单例（R12-5，2026-09-27）**：R12-4d 的 R4 探针实测证明，只要 `reset()` 会销毁
        QObject（`cls._instance = None` + `deleteLater()`），就存在「析构 × 其它线程仍持有引用」
        的窗口——`gui-race-probe` 50 轮里 2 次 `0xC0000005`（STATUS_ACCESS_VIOLATION）。
        Qt/C++ 跨线程对象管理的黄金法则：**永远不要在工作线程持有引用时销毁 QObject**。
        对象活着 ⇒ 指针恒有效；清空状态 ⇒ 逻辑上等价于「重置到初始态」。

        步骤：
        ① **关门**：置类级 `_resetting`（门闸只在本次调用期间闭合）；
        ② **清状态**：清空订阅者表与弱引用表，并 `_generation += 1`（使 reset 前排队的事件失效）；
        ③ **排空**：仅当实例属本线程时 `processEvents()` 一次，把此前排队的 deliver 跑完
           （**不使用无界的 `BlockingQueuedConnection`**——实测它在“实例线程亲和性无事件循环”时
           会把 teardown 永久挂住；跨线程残留事件由 ② 的世代号在 `deliver()` 里丢弃）；
        ④ **复位门闸**：清 `_resetting`。

        **契约（R12-5 修正）**：`reset()` **不再**保证 `instance() is not old`（旧契约正是缺陷本身），
        改为保证 **`instance() is old` 且 `old._subscribers == {}`**——即「同一实例、状态清零」。
        """
        with cls._lock:
            instance = cls._instance
            cls._resetting = True  # ① 关门（先于任何清理，杜绝新入队）
            if instance is None:
                cls._resetting = False
                return
            # ② 清状态（实例继续存活、继续可用）
            instance._subscribers.clear()
            instance._weak_subscribers.clear()
            instance._generation += 1

        try:
            # ③ 有界排空（绝不无界阻塞）
            if instance.thread() is QThread.currentThread():
                app = QCoreApplication.instance()
                if app is not None:
                    app.processEvents()
        except RuntimeError:
            # 实例可能已被 GC 或 QApplication 未就绪，安全忽略
            pass
        finally:
            with cls._lock:
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
        if EventBus._resetting:
            return
        with self._lock:
            if EventBus._resetting:
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
        """取消订阅（静止协议同 subscribe：reset 窗口内的调用为 no-op）。"""
        if EventBus._resetting:
            return
        with self._lock:
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(callback)
                except ValueError:
                    pass

    # ── 事件发布 ─────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> None:
        """发布事件（线程安全，回调在主线程执行）。

        **静止协议（R2 + R12-5 保活单例）**：reset() 窗口内（类级 `_resetting`）调用时
        **无副作用直接返回**——不入队、不抛异常，从源头切断“reset 与其它线程投递交错”。
        实例**不再被销毁**，故不存在“退役实例”状态；事件的世代号随入队携带，
        reset 之后到达的陈旧事件由 `deliver()` 丢弃（状态隔离不依赖销毁对象）。

        Args:
            event: 事件名
            data: 事件数据
        """
        if EventBus._resetting:
            return
        with self._lock:
            # 锁内二次确认：与 reset() 的临界区互斥，保证“入队”与“清状态”不交错；
            # 且入队动作本身也在临界区内 → reset() 拿到锁即意味着没有 in-flight publish 正在入队。
            if EventBus._resetting:
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
                    Q_ARG(int, self._generation),
                )

    @pyqtSlot(str, object, int)
    def deliver(self, event: str, data: Any, generation: int) -> None:
        """在主线程中执行回调（由 QMetaObject.invokeMethod 调用）。

        `generation` 为 publish 时的世代号：与当前世代不符即「reset 之前排队的陈旧事件」，
        直接丢弃——避免它在 reset 之后误触新注册的回调（等价于旧实现“换新实例”的隔离效果）。
        """
        with self._lock:
            if generation != self._generation:
                return
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
