# pilotstd/core/notification/aggregate_buffer.py
"""异步安全的通知聚合缓冲（滑动窗口策略）。"""

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class AggregateBuffer:
    """滑动窗口聚合：同类型事件在窗口内累积，到期合并为一条发送。"""

    def __init__(self, window_seconds: float, max_events: int, flush_callback: Callable) -> None:
        self._window = window_seconds
        self._max = max_events
        self._callback = flush_callback
        self._buffers: dict[str, list] = {}
        self._timers: dict[str, asyncio.TimerHandle] = {}
        self._lock = asyncio.Lock()

    async def add_event(self, event_type: str, msg) -> bool:
        """滑动窗口：新事件到达时重置倒计时。返回 True 表示达上限需立即刷新。"""
        async with self._lock:
            if event_type not in self._buffers:
                self._buffers[event_type] = []
            self._buffers[event_type].append(msg)
            # 取消旧定时器（滑动窗口：重置倒计时）
            if event_type in self._timers:
                self._timers[event_type].cancel()
            # 启动新定时器
            loop = asyncio.get_running_loop()

            def _schedule_flush(et: str = event_type) -> None:
                asyncio.ensure_future(self._flush(et))

            self._timers[event_type] = loop.call_later(self._window, _schedule_flush)
            if len(self._buffers[event_type]) >= self._max:
                return True
            return False

    async def _flush(self, event_type: str) -> None:
        """合并缓冲中的同类型事件并回调。"""
        async with self._lock:
            events = self._buffers.pop(event_type, [])
            if event_type in self._timers:
                self._timers[event_type].cancel()
                del self._timers[event_type]
        if not events:
            return
        merged = events[0]
        merged.aggregated_count = len(events)
        if len(events) > 1:
            bodies = [e.body for e in events]
            merged.body = "\n".join(f"- {b}" for b in bodies)
        self._callback(merged)

    def force_flush_all(self) -> None:
        """同步刷新所有缓冲（优雅关闭时调用）。取消定时器，立即执行回调。"""
        for et in list(self._timers.keys()):
            self._timers[et].cancel()
        for et in list(self._buffers.keys()):
            events = self._buffers.pop(et, [])
            if not events:
                continue
            merged = events[0]
            merged.aggregated_count = len(events)
            if len(events) > 1:
                bodies = [e.body for e in events]
                merged.body = "\n".join(f"- {b}" for b in bodies)
            self._callback(merged)
