# pilotstd/core/notification/aggregate_buffer.py
"""线程安全的通知聚合缓冲（定时刷新策略）。

同类事件在时间窗口内累积，到期合并为一条消息发送。
按 (event_type, target_id) 分组，支持智能摘要格式化。
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from .channel import NotificationMessage

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 5.0
DEFAULT_BATCH_SIZE = 20

# 每个条目在缓冲中的存储结构
_Entry = tuple[NotificationMessage, list[str], float]  # (msg, channels, enqueued_at)


class NotificationAggregator:
    """消息聚合器：按 (event_type, target_id) 分组，窗口内合并为一条发送。

    设计要点：
    - 线程安全（threading.Lock + threading.Timer）
    - 每组独立计时（新消息到达时重置窗口——滑动窗口）
    - 双重触发：定时器到期 OR 数量达标 → 立即发送
    - bypass_events 中的事件类型跳过聚合，实时发送
    - format_summary() 智能生成包含成功/失败/耗时统计的摘要
    - shutdown() 刷新所有残留消息，防止丢失
    """

    def __init__(
        self,
        sender_func: Callable[..., None],
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        bypass_events: set[str] | None = None,
    ) -> None:
        # sender_func 签名: (msg: NotificationMessage, target_channels: list[str]) -> None
        self._callback = sender_func
        self._window = window_seconds
        self._max = batch_size
        self._bypass = bypass_events or set()
        self._lock = threading.Lock()
        # (event_type, target_id) → list of (msg, channels, enqueued_at)
        self._buffers: dict[tuple[str, str], list[_Entry]] = {}
        self._timers: dict[tuple[str, str], threading.Timer] = {}

    # ── 公开 API ──

    def push(
        self,
        event_type: str,
        title: str,
        content: str,
        level: str = "info",
        target_id: str = "",
        channels: list[str] | None = None,
        status: str = "",
        elapsed_ms: int = 0,
    ) -> None:
        """接收一条原始消息，自动包装为 NotificationMessage 入队。

        这是最简入口——调用方无需构造 NotificationMessage 对象。
        """
        msg = NotificationMessage(
            title=title,
            body=content,
            level=level,
            event_type=event_type,
            target_id=target_id,
            status=status,
            elapsed_ms=elapsed_ms,
        )
        self.enqueue(msg, channels or [], target_id=target_id)

    def enqueue(
        self,
        msg: NotificationMessage,
        target_channels: list[str],
        target_id: str = "",
    ) -> bool:
        """入队一条 NotificationMessage。

        绕过列表中的事件直接发送并返回 True。
        普通事件入队等待聚合，返回 False。
        """
        event_type = msg.event_type
        if event_type in self._bypass:
            self._callback(msg, target_channels)
            return True

        tid = target_id or msg.target_id or ""
        key = (event_type, tid)
        now = time.monotonic()

        with self._lock:
            if key not in self._buffers:
                self._buffers[key] = []
            self._buffers[key].append((msg, target_channels, now))

            # 取消旧定时器（滑动窗口：新消息重置倒计时）
            if key in self._timers:
                self._timers[key].cancel()

            timer = threading.Timer(self._window, self._on_timer, args=(key,))
            timer.daemon = True
            timer.start()
            self._timers[key] = timer

            if len(self._buffers[key]) >= self._max:
                entries = self._buffers.pop(key, [])
                self._timers[key].cancel()
                del self._timers[key]
                self._send_merged(key, entries)
            return False

    def flush(self, event_type: str, target_id: str = "") -> None:
        """立即刷新指定分组的缓冲。"""
        key = (event_type, target_id)
        with self._lock:
            entries = self._buffers.pop(key, [])
            if key in self._timers:
                self._timers[key].cancel()
                del self._timers[key]
        if entries:
            self._send_merged(key, entries)

    def flush_all(self) -> None:
        """立即刷新所有缓冲组。"""
        keys: list[tuple[str, str]] = []
        with self._lock:
            keys = list(self._buffers.keys())
        for key in keys:
            self.flush(key[0], key[1])

    def shutdown(self) -> None:
        """优雅关闭：取消所有定时器，立即发送缓冲中所有残留消息。"""
        pending: dict[tuple[str, str], list[_Entry]] = {}
        with self._lock:
            for key in list(self._buffers.keys()):
                pending[key] = self._buffers.pop(key, [])
            for key in list(self._timers.keys()):
                self._timers[key].cancel()
            self._timers.clear()
        for key, entries in pending.items():
            if entries:
                self._send_merged(key, entries)
        if pending:
            logger.info("聚合器已关闭，刷新了 %d 组缓冲消息", len(pending))

    # ── 内部方法 ──

    def _on_timer(self, key: tuple[str, str]) -> None:
        """定时器回调：时间窗口到期，刷新缓冲。"""
        with self._lock:
            entries = self._buffers.pop(key, [])
            if key in self._timers:
                del self._timers[key]
        if entries:
            self._send_merged(key, entries)

    def _send_merged(self, key: tuple[str, str], entries: list[_Entry]) -> None:
        """合并多条消息为一条并回调发送。"""
        count = len(entries)
        first_msg, target_channels, first_ts = entries[0]
        event_type = key[0]

        merged = NotificationMessage(
            title=first_msg.title,
            body=self.format_summary(event_type, entries),
            level=self._worst_level(entries),
            standard_number=None,  # 聚合消息不再关联单条标准
            event_type=event_type,
            link=first_msg.link,
            icon=first_msg.icon,
            aggregated_count=count,
        )
        self._callback(merged, target_channels)

    # ── 摘要格式化 ──

    def format_summary(self, event_type: str, entries: list[_Entry]) -> str:
        """将多条消息合并为一条摘要文本。

        单条 → 原样返回正文。
        多条 → 统计成功/失败/总数 + 总耗时。
        """
        if len(entries) == 1:
            return entries[0][0].body

        total = len(entries)
        success_count = sum(1 for m, _, _ in entries if m.status == "success")
        failure_count = sum(1 for m, _, _ in entries if m.status == "failure")
        neutral_count = total - success_count - failure_count

        # 总耗时（最早入队 → 最晚入队）
        timestamps = [ts for _, _, ts in entries]
        elapsed_s = max(timestamps) - min(timestamps) if timestamps else 0
        # 累计单条耗时
        total_elapsed_ms = sum(m.elapsed_ms for m, _, _ in entries)

        lines: list[str] = [f"📦 {entries[0][0].title} (共 {total} 条)"]

        if success_count:
            lines.append(f"✅ 成功：{success_count} 条")
        if failure_count:
            # 列出失败项的正文摘要（截取前40字符）
            failures = [m.body[:40] for m, _, _ in entries if m.status == "failure"]
            preview = "、".join(failures[:3])
            if len(failures) > 3:
                preview += f"…等 {len(failures)} 项"
            lines.append(f"❌ 失败：{failure_count} 条 ({preview})")
        if neutral_count:
            # 中性条目也列出摘要
            neutrals = [m.body[:40] for m, _, _ in entries if not m.status]
            preview = "、".join(neutrals[:3])
            if len(neutrals) > 3:
                preview += f"…等 {len(neutrals)} 项"
            lines.append(f"📋 其他：{neutral_count} 条 ({preview})")

        if elapsed_s > 0:
            lines.append(f"⏱️ 窗口耗时：{elapsed_s:.0f}s")
        if total_elapsed_ms > 0:
            lines.append(f"⏱️ 总耗时：{total_elapsed_ms / 1000:.1f}s")

        return "\n".join(lines)

    @staticmethod
    def _worst_level(entries: list[_Entry]) -> str:
        """取所有条目中最严重的级别。"""
        order = {"info": 0, "warning": 1, "error": 2}
        worst = "info"
        worst_val = -1
        for msg, _, _ in entries:
            val = order.get(msg.level, 0)
            if val > worst_val:
                worst_val = val
                worst = msg.level
        return worst
