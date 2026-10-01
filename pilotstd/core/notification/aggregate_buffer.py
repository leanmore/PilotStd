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

# 聚合窗口默认值——与 config 的 `notification.aggregate_*` 默认值同口径：
# defaults.py 声明 aggregate_window_seconds=5 / aggregate_max_events=50，
# manager 启用聚合时会显式传入这两个值，故本处默认仅在直接构造聚合器
# （测试、独立调用）时生效。两侧若不一致，会让"直接构造"的行为与生产行为分叉。
DEFAULT_WINDOW_SECONDS = 5.0  # 首次延时：默认 5 秒（对应 aggregate_window_seconds）
MAX_WINDOW_SECONDS = 300.0  # 最大窗口：5 分钟后强制发送（硬上限，无对应配置键）
DEFAULT_BATCH_SIZE = 50  # 对应 aggregate_max_events

# 分组键中「事件类型」与「关联实体」的分隔符。
# 用 US（Unit Separator，U+001F）而非普通字符：事件类型与 target_id 均来自业务
# 标识（标准号、任务名），任何可见字符都可能在 target_id 中出现，用不可见控制字符
# 才能保证 split 结果确定。
_GROUP_SEP = "\x1f"

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
        普通事件按「事件类型 × 关联实体」入队等待聚合，返回 False。

        固定窗口：第一条消息启动计时器，窗口内新消息追加到缓冲区，
        不重置计时器。默认 5 秒首次触发（同 aggregate_window_seconds），
        最长 300 秒强制发送。
        """
        event_type = msg.event_type
        if event_type in self._bypass:
            self._callback(msg, target_channels)
            return True

        # 兼容 push() 旧签名：显式传入的 target_id 仅在消息自身为空时补齐，
        # 保证分组键只有一个来源（避免两处不一致导致分组行为不可预测）。
        if target_id and not msg.target_id:
            msg.target_id = target_id

        group = self._group_key(msg)
        now = time.monotonic()

        with self._lock:
            if group not in self._buffers:
                self._buffers[group] = []
            self._buffers[group].append((msg, target_channels, now))

            # 如果是该分组的第一批消息，启动计时器
            if group not in self._timers or self._timers[group] is None:
                self._window_start[group] = now
                timer = threading.Timer(self._window, self._on_timer, args=(group,))
                timer.daemon = True
                timer.start()
                self._timers[group] = timer

            # 数量达标 → 立即发送（按分组各自计数）
            if len(self._buffers[group]) >= self._max:
                entries = self._buffers.pop(group, [])
                t = self._timers.pop(group, None)
                if t:
                    t.cancel()
                self._window_start.pop(group, None)
                self._send_merged(event_type, entries)
            return False

    def flush(self, event_type: str, target_id: str = "") -> None:
        """立即刷新缓冲。

        指定 `target_id` 时只刷新该实体的分组；省略时刷新该事件类型的**全部**实体分组。
        """
        with self._lock:
            groups = [
                g
                for g in self._buffers
                if event_type in self._events_in_group(g)
                and (not target_id or self._group_entity(g) == target_id)
            ]
            drained: list[tuple[str, list[_Entry]]] = []
            for group in groups:
                drained.append((group, self._buffers.pop(group, [])))
                t = self._timers.pop(group, None)
                if t:
                    t.cancel()
                self._window_start.pop(group, None)
        for group, entries in drained:
            if entries:
                self._send_merged(self._events_in_group(group).pop(), entries)

    def flush_all(self) -> None:
        """立即刷新所有缓冲组（单次持锁排空，避免逐组重复加锁）。"""
        with self._lock:
            drained = [(g, self._buffers.pop(g, [])) for g in list(self._buffers.keys())]
            for t in list(self._timers.values()):
                if t:
                    t.cancel()
            self._timers.clear()
            self._window_start.clear()
        for group, entries in drained:
            if entries:
                events = self._events_in_group(group)
                self._send_merged(next(iter(events)) if events else group, entries)

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
                events = self._events_in_group(key)
                self._send_merged(next(iter(events)) if events else key, entries)
        if pending:
            logger.info("聚合器已关闭，刷新了 %d 组缓冲消息", len(pending))

    # ── 分组键 ──

    def _group_key(self, msg: NotificationMessage) -> str:
        """分组键 = 事件类型 + 关联实体（`target_id`）。

        实体维度让"同一事件类型、不同业务对象"的通知各自成组：
        例如同一批扫描里 task_a 与 task_b 的完成通知不应被合并成一条
        （否则用户只看到"聚合通知（2 条）"，无法分辨各自结果）。

        回退：`target_id` 缺失（空串或纯空白）时退化为纯事件类型分组——
        此时同类通知仍聚合，绝不把**不同**实体混为一组。
        """
        entity = (msg.target_id or "").strip()
        return f"{msg.event_type}{_GROUP_SEP}{entity}" if entity else msg.event_type

    @staticmethod
    def _events_in_group(group: str) -> set[str]:
        """从分组键还原事件类型集合（无实体时为单元素集合）。"""
        return {group.split(_GROUP_SEP, 1)[0]}

    @staticmethod
    def _group_entity(group: str) -> str:
        """从分组键还原关联实体；无实体分组返回空串。"""
        _, sep, entity = group.partition(_GROUP_SEP)
        return entity if sep else ""

    # ── 内部方法 ──

    def _on_timer(self, group: str) -> None:
        """定时器回调：检查窗口 → 发送或续期。

        参数是**分组键**（事件类型 × 关联实体），非单纯事件类型：
        续期与发送都必须按同一分组进行，否则会跨实体串组。
        """
        with self._lock:
            start = self._window_start.get(group)
            if start is not None:
                elapsed = time.monotonic() - start
                if elapsed < MAX_WINDOW_SECONDS:
                    # 未到最大窗口 → 发送当前缓冲，续期计时器
                    entries = self._buffers.pop(group, [])
                    if entries:
                        events = self._events_in_group(group)
                        self._send_merged(next(iter(events)), entries)
                    # 续期：新计时器继续轮询同一分组
                    timer = threading.Timer(self._window, self._on_timer, args=(group,))
                    timer.daemon = True
                    timer.start()
                    self._timers[group] = timer
                    return
            # 窗口已满或开始标记缺失 → 强制发送并清空
            entries = self._buffers.pop(group, [])
            self._timers.pop(group, None)
            self._window_start.pop(group, None)
        if entries:
            events = self._events_in_group(group)
            self._send_merged(next(iter(events)) if events else group, entries)

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
