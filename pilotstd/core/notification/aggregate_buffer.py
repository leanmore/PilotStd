# 模块：项目/核心//_缓冲区脚本
"""服务端通知聚合缓冲（固定窗口 + 首次延时策略）。

职责边界（三套通知聚合/去重机制之一，禁止越界）：
- **本模块负责**：服务端**按时间窗口聚合**——把 `manager.send_event` 触发的、
  异步到达的多条通知，按「事件类型 × 关联实体」累积后合并为一条摘要投递。
- **输入**：已构建好的 `NotificationMessage`（构建器产出，本模块不构造消息）。
- **输出**：聚合后的摘要消息（经 `sender_func` 回调），或单条原样投递。
- **本模块不负责**：单条消息格式化（→ `renderer.py`）、渠道路由与发送（→ `manager._do_send`
  与 `channels/`）、静音时段判断（→ `manager._is_quiet_hours`）、桌面托盘去重
  （→ `core/notification_aggregator.py` 与 `platform/notify.py:_check_dedup`）。
- **不派生 `target_id`**：本模块只消费调用方传入的实体标识；桌面链路的实体标识由
  `core/notification_aggregator._extract_topic` 从标题映射而来。

与 `core/notification_aggregator.NotificationAggregator` 的关系：**两条独立链路，不共享状态**。
本模块服务服务端通知（Web / Webhook / 定时任务）；后者服务 PyQt 桌面托盘通知，
是持有本模块实例并委托 `push()` 的适配层。

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
from copy import deepcopy

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

# 续期阈值（时序专项），随窗口缩放而非固定值：
# - `_TIMER_SLEEP_RATIO`：剩余时间超过 `窗口 × 该比例` 才值得再开一轮定时器。
#   固定阈值不可用——相对 `MAX_WINDOW_SECONDS` 很小的窗口（如测试用 0.05s）下，
#   固定 0.1s 会大于窗口本身，导致提前强制发送、失去精度意义。
# - `_MAX_TIMER_SLEEP_CAP`：比例阈值的上限，避免大窗口（生产 5s）下最后一轮过长。
_MIN_TIMER_SLEEP = 0.001
_TIMER_SLEEP_RATIO = 0.1
_MAX_TIMER_SLEEP_CAP = 0.05

# 多条聚合摘要的排版口径
_PREVIEW_ITEMS = 5  # 摘要中逐条列出的最大条数
_PREVIEW_CHARS = 60  # 每条摘要保留的首行字符数

# 每个条目在缓冲中的存储结构
_Entry = tuple[NotificationMessage, list[str], float]  # (msg, channels, enqueued_at)


class NotificationAggregator:
    """消息聚合器：按 event_type 分组，固定窗口内合并为一条发送。

    设计要点：
    - 线程安全（threading.Lock + threading.Timer）
    - 固定窗口 + 首次延时：第一批消息按窗口触发，强制发送硬上界 MAX_WINDOW_SECONDS
    - 双重触发：定时器到期 OR 数量达标 → 立即发送
    - bypass_events 中的事件类型跳过聚合，实时发送
    - 摘要生成器基于结构块渲染生成标准化摘要（单条全文/多条统计）
    - shutdown() 刷新所有残留消息，防止丢失
    - **时序契约**：从窗口起算到达强制发送不超过 MAX_WINDOW_SECONDS + ε
      （续期基于剩余时间；发送在锁外执行，其耗时不再叠加到后续间隔）
    """

    def __init__(
        self,
        sender_func: Callable[..., None],
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        bypass_events: set[str] | None = None,
        send_delay: float = 0.0,
    ) -> None:
        self._callback = sender_func
        self._window = window_seconds
        self._max = batch_size
        self._bypass = bypass_events or set()
        # 测试钩子：人为给每次发送注入延迟，用于验证"回调超时后不累积漂移"。
        # 生产恒为 0.0（默认值），不改变任何运行时行为。
        self._send_delay = send_delay
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
        **①批次路径的例外（2026-10-05 分组键分层）**：批次组的键按设计**不含实体**
        （`_group_entity` 对 `1<SEP>…` 恒返回 `""`），若仍按"实体相等"过滤，这类组**永远刷不出来**。
        因此：传入 `target_id` 时，**批次组一律视为匹配**（其语义是"整批一条"，本就无实体可筛）。
        """
        with self._lock:
            groups = [
                g
                for g in self._buffers
                if event_type in self._events_in_group(g)
                and (
                    not target_id
                    or self._group_entity(g) == target_id
                    or g.startswith(f"1{_GROUP_SEP}")  # ①批次组：无实体维度，按实体筛选不适用
                )
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
        """分组键 = **模式前缀 + 收敛类/事件类型 + （可选）关联实体**。

        2026-10-05 通知聚合改造（分组键分层，裁定口径）——两条路径**按是否有批次标识分流**：
        · **①批量导入路径**（`correlation_id` 非空）：键 = `批次 × notify_event`
          ⇒ 一次导入（同一批次）的查询/下载/规范化/存档通知收敛为**同一条**；
          **不含 `target_id`**：批次内每个标准的失败明细走 payload 的 `failed_items`（不靠分组键拆分）。
        · **②日常操作路径**（`correlation_id` 为空）：键 = `notify_event × target_id`
          ⇒ 保留实体维度（同一事件类型下 task_a / task_b 各自成组，绝不混为一组）。
        为什么用模式前缀 `1`/`2`：让键可自解释、避免两条路径的键**跨模式撞车**；
        为什么 `notify_event` 为空时回退 `event_type`：字段契约允许"尚未映射"（见 channel.py 注释），
        直拼空串会把所有未映射消息并进同一组。
        """
        notify = (getattr(msg, "notify_event", "") or "").strip() or msg.event_type
        entity = (msg.target_id or "").strip()
        batch = (getattr(msg, "correlation_id", "") or "").strip()
        if batch:
            return f"1{_GROUP_SEP}{batch}{_GROUP_SEP}{notify}"
        return f"2{_GROUP_SEP}{notify}{_GROUP_SEP}{entity}" if entity else f"2{_GROUP_SEP}{notify}"

    @staticmethod
    def _events_in_group(group: str) -> set[str]:
        """从分组键还原**收敛类/事件类型**（代表事件与 formatter 查找依赖它）。

        键格式（2026-10-05 分层后）：
        · ①批次路径 `1<SEP>批次<SEP>收敛类` ⇒ 取**最后一段**（批次号在中间，不是收敛类）；
        · ②常规路径 `2<SEP>收敛类[<SEP>实体]` ⇒ 取**第 2 段**。
        为什么按模式分支：两路径的段位语义不同，同一套下标会取到批次号（回归实例见
        `tests/test_aggregate_buffer.py::test_group_key_batch_path_uses_correlation_id`）。
        """
        parts = group.split(_GROUP_SEP)
        if parts[0] == "1":
            return {parts[-1]} if len(parts) >= 3 else {group}
        return {parts[1]} if len(parts) > 1 else {group}

    @staticmethod
    def _group_entity(group: str) -> str:
        """从分组键还原关联实体；**②路径的最后一段**才是实体，①路径无实体（返回空串）。"""
        parts = group.split(_GROUP_SEP)
        if len(parts) >= 3 and parts[0] == "2":
            return parts[2]
        return ""

    # ── 内部方法 ──

    def _on_timer(self, group: str) -> None:
        """定时器回调：检查窗口 → 发送或**按剩余时间**续期。

        参数是**分组键**（事件类型 × 关联实体），非单纯事件类型：
        续期与发送都必须按同一分组进行，否则会跨实体串组。

        时序契约（专项修复）：从 `_window_start[group]` 起算，强制发送应落在
        `MAX_WINDOW_SECONDS` 之内。原实现每次续期都排**完整窗口**，而
        `elapsed < MAX` 只保证"下一次续期会超时"，那次续期可能**跨过上界最多一个
        窗口 w** → 越界上界为 `MAX + w`（生产 w=5s / MAX=300s 即 305s；实测
        window=0.07/max=0.3 时越界到 0.35s）。故末轮必须只睡**到上界的剩余时间**。

        发送一律在**锁外**执行：网络 IO 耗时不得阻塞其它分组的入队与回调。
        """
        force_entries: list[_Entry] | None = None
        case_entries: list[_Entry] | None = None
        now = time.monotonic()
        with self._lock:
            start = self._window_start.get(group)
            if start is None:
                # 窗口起点缺失（异常路径）：用当前时刻兜底起算，避免"无起点即立即发送"
                # 把刚入队的消息提前吐出去。
                start = now
                self._window_start[group] = start

            elapsed = now - start
            remaining = MAX_WINDOW_SECONDS - elapsed
            if remaining > min(self._window * _TIMER_SLEEP_RATIO, _MAX_TIMER_SLEEP_CAP):
                # 还早：取出当前缓冲并续期——只睡"剩余时间"与"满窗口"中的较小者，
                # 使末轮不跨越上界。发送留到锁外。
                case_entries = self._buffers.pop(group, [])
                self._schedule_next(group, min(self._window, remaining))
            else:
                # 剩余不足以再开一轮 → 本组立即强制发送并清空（原实现在此处仍会续期）
                force_entries = self._buffers.pop(group, [])
                self._timers.pop(group, None)
                self._window_start.pop(group, None)

        # 发送全部在**锁外**执行
        if case_entries:
            events = self._events_in_group(group)
            self._send_merged(next(iter(events)), case_entries, start)
        if force_entries:
            events = self._events_in_group(group)
            elapsed = time.monotonic() - start
            logger.warning(
                "通知聚合已达最大窗口，强制发送: group=%s 实际耗时 %.0f ms（上界 %.0f ms，偏差 %+.0f ms）",
                group,
                elapsed * 1000,
                MAX_WINDOW_SECONDS * 1000,
                (elapsed - MAX_WINDOW_SECONDS) * 1000,
            )
            self._send_merged(next(iter(events)) if events else group, force_entries, start)

    def _schedule_next(self, group: str, delay: float) -> None:
        """为分组安排下一次回调（调用方须持有 `_lock`）。

        续期失败不得让该分组**永久滞留**：兜底为记录告警并清除窗口起点，
        使下一次 `enqueue` 重新起算窗口（消息仍在 `_buffers` 中，不会丢失）。
        """
        try:
            timer = threading.Timer(max(delay, _MIN_TIMER_SLEEP), self._on_timer, args=(group,))
            timer.daemon = True
            timer.start()
            self._timers[group] = timer
            logger.debug(
                "通知聚合续期: group=%s 下次触发 %.0f ms 后（窗口 %.0f ms，硬上界 %.0f ms）",
                group,
                max(delay, _MIN_TIMER_SLEEP) * 1000,
                self._window * 1000,
                MAX_WINDOW_SECONDS * 1000,
            )
        except Exception:
            logger.warning("通知聚合续期失败，清除窗口起点以便重新起算: group=%s", group, exc_info=True)
            self._timers.pop(group, None)
            self._window_start.pop(group, None)

    def _send_merged(self, event_type: str, entries: list[_Entry], start: float | None = None) -> None:
        """合并多条消息为一条并回调发送（单条与多条统一流程，无特殊分支）。

        正统设计：
        1. 保留第一条消息的结构块作为骨架（单条/多条一律保留，绝不丢弃）；
        2. 摘要正文由摘要生成器基于结构块渲染（或事件特定格式化器）；
        3. 构造合并消息：结构块始终在场，正文作为摘要文本。

        `start` 为该分组的窗口起点（可为 None）：给出时记录结构化时序
        （期望上界 / 实际耗时 / 偏差 ms），供生产观测聚合是否逼近硬上界。
        """
        if not entries:
            return

        if start is not None:
            elapsed = time.monotonic() - start
            logger.debug(
                "通知聚合发送时序: event=%s 条数=%d 窗口耗时=%.0f ms 上界=%.0f ms 偏差=%+.0f ms",
                event_type,
                len(entries),
                elapsed * 1000,
                MAX_WINDOW_SECONDS * 1000,
                (elapsed - MAX_WINDOW_SECONDS) * 1000,
            )
        # 测试钩子注入的发送延迟（生产恒为 0，见 __init__）
        if self._send_delay:
            time.sleep(self._send_delay)

        count = len(entries)
        first_msg, target_channels, _first_ts = entries[0]

        # 1. 合并**全部**条目的结构块（按到达序拼接）——Z-21 裁定（2026-10-05）。
        # 为什么不再"只保留第一条作为骨架"：旧实现在此处丢弃第 2..N 条的 blocks，仅留 first_msg 的块，
        # 于是聚合后用户**只看得到第一条的明细** ⇒ 需求①（失败明细：失败类型×标准号×标准名×总数）
        # 与需求②（时间窗内合并但不得丢信息）双双落空（现状取证见 08-聚合设计.md §七 K-2）。
        # 为什么不会产生 N 个标题：标题来自 NotificationMessage.title 字段并在渲染层单独渲染
        # （见 renderer.py 的标题渲染），blocks 只承载正文块 ⇒ 全量拼接不会重复标题。
        # 来源可追溯：顺序＝entries 的到达序（块与其来源消息的对应由该顺序隐含表达；
        # 如需显式溯源标注，属后续增强，见 08-聚合设计.md §E8）。
        merged_blocks = [blk for entry_msg, _ch, _ts in entries for blk in (entry_msg.blocks or [])]

        # 2. 生成标准化摘要（事件特定格式化器优先，否则基于结构块渲染）
        formatter = self._formatters.get(event_type)
        if formatter:
            summary_text = formatter(event_type, entries, count)
        else:
            summary_text = self._build_summary(entries)

        # 3. 构造合并消息：结构块始终保留，正文作为摘要
        #
        # 阶段 1a（2026-10-02）：显式搬运通知身份字段。
        # 本构造是**重造**消息（不是就地修改），未列出的字段会取 dataclass 默认值——
        # 即：聚合后的消息若忘了搬运，message_id/correlation_id 会**永远为空**，
        # 而单条直发路径正常，属"只在聚合时静默丢身份"的隐性缺陷。故新字段必须显式搬运。
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
            # 首条消息的身份代表整组（correlation_id 是"同一次运行"的键，组内应相同）
            message_id=first_msg.message_id,
            correlation_id=first_msg.correlation_id,
            # 投递态/回执态**重置**而非沿用：这条是新消息、尚未投递，沿用会让日志谎报状态
            delivery_status="pending",
            ack_status="none",
            # 阶段 1b：任务视角。task_id / notify_event / content_type 与 1a 同款，
            # 取首条——三者在本分组内是**不变量**：分组键是 event_type × target_id，
            # 而 notify_event/content_type 由 event_type 派生、task_id 由同一实体派生。
            task_id=first_msg.task_id,
            notify_event=first_msg.notify_event,
            content_type=first_msg.content_type,
            # task_context 取**首条**而非合并：理由同上（分组键保证组内同实体同事件，
            # 上下文应一致），且"合并"需要定义键冲突的仲裁规则（首个非空？最坏值？），
            # 那是一套无实际收益的复杂度；若组内上下文确实不同，那说明分组键选错了。
            # 用 dict(...) 浅拷贝：first_msg 可能在窗口期内被调用方继续复用/修改。
            task_context=dict(first_msg.task_context),
            # 阶段 1c：交互能力。
            # actions / attachments 取**首条深拷贝**——聚合后是摘要，用户点进原消息再操作；
            # 多条各带 retry 会变成混乱的多按钮组。深拷贝（而非浅拷贝）的理由：
            # 元素是 ActionSpec/AttachmentSpec，其 args 是可变 dict，浅拷贝仍会共享它
            # ——后续修改原消息的 args 会污染合并消息。
            actions=deepcopy(first_msg.actions),
            attachments=deepcopy(first_msg.attachments),
            # channel_message_ids / callback_data **重置**：与 1a 的
            # delivery_status/ack_status 同理——这条是新消息、尚未投递，
            # 既没有渠道消息 ID，也没有可用的回调载荷；沿用会让阶段 3 对着
            # 一个不属于本消息的 ID 去编辑消息。
            callback_data="",
            channel_message_ids={},
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
