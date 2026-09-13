# 模块：项目/核心//_缓冲区脚本
"""线程安全的通知聚合缓冲（固定窗口 + 首次延时策略）。

同类事件在固定窗口内累积，1 分钟首次触发，5 分钟强制发送。
按 event_type 分组，支持智能摘要和事件特定格式化。

聚合正统设计（无界编码治理样板 · 第二期）：
- 单条与多条统一走合并发送同一流程，禁止"单条直通"特殊分支；
- 合并后的消息始终保留第一条消息的结构块作为骨架（绝不丢弃）；
- 摘要正文基于结构块渲染生成，禁止对原始正文做截断；
- 事件特定格式化器（注册的格式化回调）优先于通用摘要。
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from pilotstd.i18n import t

from .channel import NotificationMessage
from .renderer import _fallback_text

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 60.0  # 首次延时：1分钟后触发
MAX_WINDOW_SECONDS = 300.0  # 最大窗口：5分钟后强制发送
DEFAULT_BATCH_SIZE = 20

# 多条聚合摘要的排版口径
_PREVIEW_ITEMS = 5  # 摘要中逐条列出的最大条数
_PREVIEW_CHARS = 60  # 每条摘要保留的首行字符数

# 每个条目在缓冲中的存储结构
_Entry = tuple[NotificationMessage, list[str], float]  # (msg, channels, enqueued_at)


class NotificationAggregator:
    """消息聚合器：按 event_type 分组，固定窗口内合并为一条发送。

    设计要点：
    - 线程安全（threading.Lock + threading.Timer）
    - 固定窗口 + 首次延时：第一批消息 1 分钟后触发，总窗口 5 分钟
    - 双重触发：定时器到期 OR 数量达标 → 立即发送
    - bypass_events 中的事件类型跳过聚合，实时发送
    - 摘要生成器基于结构块渲染生成标准化摘要（单条全文/多条统计）
    - shutdown() 刷新所有残留消息，防止丢失
    """

    def __init__(
        self,
        sender_func: Callable[..., None],
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        bypass_events: set[str] | None = None,
    ) -> None:
        self._callback = sender_func
        self._window = window_seconds
        self._max = batch_size
        self._bypass = bypass_events or set()
        self._lock = threading.Lock()
        # 说明：_→(,渠道,队列_)
        self._buffers: dict[str, list[_Entry]] = {}
        self._timers: dict[str, threading.Timer | None] = {}
        self._window_start: dict[str, float] = {}
        # 事件特定格式化回调：_→(,)→
        self._formatters: dict[str, Callable[..., str]] = {}
        # 摘要渲染器：聚合消息正文基于结构块渲染生成（基类渲染器，无渠道转义）
        from .renderer import BlockRenderer

        self._renderer = BlockRenderer()

    def register_formatter(self, event_type: str, formatter: Callable[..., str]) -> None:
        """注册事件特定的聚合摘要格式化回调。"""
        self._formatters[event_type] = formatter

    # ──公开接口──

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

        固定窗口：第一条消息启动计时器，窗口内新消息追加到缓冲区，
        不重置计时器。1 分钟后首次触发，5 分钟总窗口后强制发送。
        """
        event_type = msg.event_type
        if event_type in self._bypass:
            self._callback(msg, target_channels)
            return True

        now = time.monotonic()

        with self._lock:
            if event_type not in self._buffers:
                self._buffers[event_type] = []
            self._buffers[event_type].append((msg, target_channels, now))

            # 如果是第一批消息，启动计时器
            if event_type not in self._timers or self._timers[event_type] is None:
                self._window_start[event_type] = now
                timer = threading.Timer(self._window, self._on_timer, args=(event_type,))
                timer.daemon = True
                timer.start()
                self._timers[event_type] = timer

            # 数量达标 → 立即发送
            if len(self._buffers[event_type]) >= self._max:
                entries = self._buffers.pop(event_type, [])
                t = self._timers.pop(event_type, None)
                if t:
                    t.cancel()
                self._window_start.pop(event_type, None)
                self._send_merged(event_type, entries)
            return False

    def flush(self, event_type: str, target_id: str = "") -> None:
        """立即刷新指定事件类型的缓冲。"""
        with self._lock:
            entries = self._buffers.pop(event_type, [])
            t = self._timers.pop(event_type, None)
            if t:
                t.cancel()
            self._window_start.pop(event_type, None)
        if entries:
            self._send_merged(event_type, entries)

    def flush_all(self) -> None:
        """立即刷新所有缓冲组。"""
        keys: list[str] = []
        with self._lock:
            keys = list(self._buffers.keys())
        for key in keys:
            self.flush(key)

    def shutdown(self) -> None:
        """优雅关闭：取消所有定时器，立即发送缓冲中所有残留消息。"""
        pending: dict[str, list[_Entry]] = {}
        with self._lock:
            for key in list(self._buffers.keys()):
                pending[key] = self._buffers.pop(key, [])
            for key in list(self._timers.keys()):
                t = self._timers.pop(key, None)
                if t:
                    t.cancel()
            self._window_start.clear()
        for key, entries in pending.items():
            if entries:
                self._send_merged(key, entries)
        if pending:
            logger.info("聚合器已关闭，刷新了 %d 组缓冲消息", len(pending))

    # ── 内部方法 ──

    def _on_timer(self, event_type: str) -> None:
        """定时器回调：检查窗口 → 发送或续期。"""
        with self._lock:
            start = self._window_start.get(event_type)
            if start is not None:
                elapsed = time.monotonic() - start
                if elapsed < MAX_WINDOW_SECONDS:
                    # 未到最大窗口 → 发送当前缓冲，续期计时器
                    entries = self._buffers.pop(event_type, [])
                    if entries:
                        self._send_merged(event_type, entries)
                    # 续期：新计时器继续轮询
                    timer = threading.Timer(self._window, self._on_timer, args=(event_type,))
                    timer.daemon = True
                    timer.start()
                    self._timers[event_type] = timer
                    return
            # 窗口已满或开始标记缺失 → 强制发送并清空
            entries = self._buffers.pop(event_type, [])
            self._timers.pop(event_type, None)
            self._window_start.pop(event_type, None)
        if entries:
            self._send_merged(event_type, entries)

    def _send_merged(self, event_type: str, entries: list[_Entry]) -> None:
        """合并多条消息为一条并回调发送（单条与多条统一流程，无特殊分支）。

        正统设计：
        1. 保留第一条消息的结构块作为骨架（单条/多条一律保留，绝不丢弃）；
        2. 摘要正文由摘要生成器基于结构块渲染（或事件特定格式化器）；
        3. 构造合并消息：结构块始终在场，正文作为摘要文本。
        """
        if not entries:
            return

        count = len(entries)
        first_msg, target_channels, _first_ts = entries[0]

        # 1. 保留第一条消息的结构块作为骨架（单条/多条统一）
        merged_blocks = first_msg.blocks or []

        # 2. 生成标准化摘要（事件特定格式化器优先，否则基于结构块渲染）
        formatter = self._formatters.get(event_type)
        if formatter:
            summary_text = formatter(event_type, entries, count)
        else:
            summary_text = self._build_summary(entries)

        # 3. 构造合并消息：结构块始终保留，正文作为摘要
        merged = NotificationMessage(
            title=first_msg.title,
            body=summary_text,
            blocks=merged_blocks,  # 核心：绝不丢弃
            level=self._worst_level(entries),
            standard_number=first_msg.standard_number,
            event_type=event_type,
            link=first_msg.link,
            icon=first_msg.icon,
            aggregated_count=count,
        )
        self._callback(merged, target_channels)

    # ── 摘要格式化 ──

    def _build_summary(self, entries: list[_Entry]) -> str:
        """摘要生成：单条渲染全文，多条渲染统计加明细。

        统一基于结构块渲染（非原始正文截断），保证任何路径下摘要非空：
        - 单条：渲染全文；渲染结果为空则回退标题，再兜底固定文案。
        - 多条：统计头加每条渲染首行（前 60 字符）；明细超过 5 条时
          截断显示 "… 等 N 条"（v1.1 增强：控制单条通知体积）。
        """
        if len(entries) == 1:
            msg = entries[0][0]
            rendered = self._renderer.render(msg)
            return rendered or msg.title or _fallback_text()

        lines: list[str] = [t("notification.aggregated.body.header").format(n=len(entries))]
        for msg, _ch, _ts in entries[:_PREVIEW_ITEMS]:
            rendered = self._renderer.render(msg)
            first_line = (
                rendered.split("\n")[0].strip() if rendered else (msg.title or _fallback_text())
            )
            lines.append(
                t("notification.aggregated.body.item").format(line=first_line[:_PREVIEW_CHARS])
            )
        if len(entries) > _PREVIEW_ITEMS:
            lines.append(t("notification.aggregated.body.more").format(n=len(entries)))
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
