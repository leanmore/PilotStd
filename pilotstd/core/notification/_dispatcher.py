# 模块：项目/核心//发送编排脚本
"""发送编排（步 C B2：从 `manager.py` 拆出）。

**为什么是模块级函数而不是新类**：`tests/test_aggregate_buffer.py` 把
`NotificationManager._validate_message` 取出来**绑定到 `MagicMock(spec=…)` 上执行真实逻辑**
（`__get__(mgr)`），并以 `NotificationManager.send_event(mgr, …)` 直接调用类属性。若把这些
成员改为"转发到 `self._dispatcher.<同名>`"，`self` 是 Mock 时只会得到 Mock，**真实逻辑不再执行**
（04 §1.3.3 的硬规则："必须保持类属性是函数，且转发体不得访问实例独有属性"）。
故本模块以**宿主入参**的形式实现编排：`manager` 侧只剩一行同名委托，
对"绑定到 Mock 的类属性调用"与"实例级替换（`mgr._send_now = …`）"两种用法都保持原语义。

**调用约定**：能力一律经 `host.<名字>(…)` **动态取用**（不是构造期捕获的绑定方法），
因此测试里替换 `host._send_now` / `host._do_send` / `host._build_message` / `host.send_event`
仍然生效——这是 `tests/test_delivery_health.py`、`tests/test_aggregate_buffer.py` 的既有契约。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pilotstd.i18n import t

from .channel import NotificationMessage

logger = logging.getLogger(__name__)


def send_event(
    host: Any,
    event_type: str,
    event_data: dict[str, Any],
    bypass_aggregation: bool = False,
    target_channels: list[str] | None = None,
) -> None:
    """根据策略表分发通知到各渠道（经过聚合器缓冲）。

    优先从 notification_policy 表读取渠道事件订阅，
    若表为空则回退到 config.json 的 notification.rules 配置。
    bypass_aggregation=True 时跳过聚合缓冲，实时发送（供紧急告警事件使用）。
    target_channels 非空时**跳过策略查询**、改用调用方指定渠道——供"投递失败告警"
    使用：故障渠道很可能就是问题本身，必须能定向发给**旁路**渠道（策略表无法表达
    "除某渠道外的全部渠道"）。
    """
    # W2（共享事件按端分流）：桌面端把事件落到**本地信号**（托盘气泡）。
    # 必须在 `_enabled` 早退**之前**——渠道开关（默认关闭）与"本端是否可见"是两件事；
    # 若先早退，这些事件在 Windows 端就"两头都不落"（Docker 端的渠道/Web 由那边的 manager 负责）。
    # 本地信号看的是**构建器原始产出**（不施加三层模型投影，那是渠道侧阶段）。
    if host._local_sink is not None:
        host._local_sink(host._build_message(event_type, event_data))
    if not host._enabled:
        logger.debug(t("notification.manager.skip_disabled").format(event=event_type))
        return
    if target_channels is None:
        target_channels = host._policy.get_channels_for_event(host._user_id, event_type)
    if not target_channels:
        logger.info(t("notification.manager.skip_no_channels").format(event=event_type))
        return

    msg = host._build_message(event_type, event_data)
    # 三层模型投影回填（阶段 2b-接入）：默认 stage=1 → 不生效，行为零变化。
    # 实现在 _manager_ops（并入本模块会超 G-010 的 500 阻断线）。
    host.ops.apply_mapping(msg, event_type, event_data)
    # 构建器契约校验：空消息拦截（失败仅记错误日志，不中断主业务流程）
    try:
        host._validate_message(msg, event_type)
    except ValueError as e:
        logger.error(t("notification.manager.validate_failed").format(event=event_type, error=e))
        return
    host._do_send(msg, target_channels, bypass_aggregation=bypass_aggregation)


def validate_message(host: Any, msg: NotificationMessage, event_type: str) -> None:
    """构建器产出契约校验：确保任何路径下消息都不会为空。

    校验规则：
    - 结构块 / 正文 / 标题至少一项非空，否则抛出数值错误（表示构建器契约被破坏）；
    - 仅有结构块无正文时记录调试日志（聚合摘要依赖正文，提示开发者补全）。

    调用方（事件发送入口）捕获数值错误并记录错误日志，不向上抛——
    校验失败不得导致收藏/下载/抓取等主业务流程崩溃。
    """
    del host  # 纯函数：不依赖宿主状态（保留形参以统一调用约定）
    has_blocks = bool(msg.blocks)
    has_body = bool(msg.body and msg.body.strip())
    has_title = bool(msg.title and msg.title.strip())

    if not (has_blocks or has_body or has_title):
        raise ValueError(
            f"Builder for '{event_type}' produced an empty Message. "
            "At least one of blocks/body/title must be non-empty."
        )

    if has_blocks and not has_body:
        logger.debug("Builder for '%s' has blocks but no body", event_type)


def do_send(
    host: Any,
    msg: NotificationMessage,
    target_channels: list[str],
    bypass_aggregation: bool = False,
) -> None:
    """逐渠道发送：静音期暂存 → 聚合器入队 → 合并后发送。"""
    if host._is_quiet_hours():
        host._enqueue_notification(msg, target_channels)
        return
    if host.aggregator is not None and not bypass_aggregation:
        # 仅做「是否聚合」的分支决策，实际聚合全部委托给 AggregateBuffer
        # （窗口累积、分组、摘要生成都在那边），管理器不重复实现合并逻辑。
        host.aggregator.enqueue(msg, target_channels, target_id=msg.target_id)
    else:
        host._send_now(msg, target_channels)


def send_now(host: Any, msg: NotificationMessage, target_channels: list[str]) -> None:
    """实际执行发送（写日志 + 渠道推送）。"""
    event_type = msg.event_type
    for ch_name in target_channels:
        channel = host._channels.get(ch_name)
        sent_at = datetime.now().isoformat()
        if channel is None:
            host._log(
                event_type,
                ch_name,
                msg,
                "failed",
                t("notification.manager.channel_unavailable").format(ch=ch_name),
                sent_at,
            )
            continue
        try:
            ok = channel.send(msg)
            # 读取渠道错误详情透传具体原因，无详情时回退默认文案
            if ok:
                err_msg = ""
            else:
                err_msg = getattr(channel, "last_error", "") or t(
                    "notification.manager.send_failed_no_detail"
                )
            host._log(event_type, ch_name, msg, "success" if ok else "failed", err_msg, sent_at)
            host._record_delivery(ch_name, ok)
        except Exception as e:
            host._log(event_type, ch_name, msg, "failed", str(e), sent_at)
            host._record_delivery(ch_name, False)


def record_delivery(host: Any, channel: str, ok: bool) -> None:
    """记录一次投递结果，并在越过阈值时发出"通知投递失败"告警。

    **不回环**：告警投递期间置 `_sending_delivery_alert`，期间的结果**不再计入健康度**
    （否则告警失败又触发新告警，无限递归）。见 `send_delivery_alert`。
    """
    if host.delivery_health is None or host._sending_delivery_alert:
        return
    host.delivery_health.record(channel, ok)
    if ok:
        return
    verdict = host.delivery_health.evaluate(channel)
    if verdict is None:
        return
    reason, samples, failures = verdict
    host._send_delivery_alert(channel, reason, samples, failures)


def send_delivery_alert(
    host: Any, channel: str, reason: str, samples: int, failures: int
) -> None:
    """投递"通知投递失败"告警。

    目标渠道：**除故障渠道外的所有已启用渠道**——故障渠道很可能是问题本身，
    优先走旁路。若无旁路可用，仍投向故障渠道（可能也失败，但会在通知日志
    留下"曾试图告警"的痕迹，好过完全静默）。

    `bypass_aggregation=True`：告警不能等 5 秒聚合窗口（也可能被静默时段压后），
    与安全告警同理——"通知已经坏了"这件事需要立刻说出来。
    """
    host._sending_delivery_alert = True
    try:
        targets = [c for c in host._channels if c != channel] or [channel]
        host.send_event(
            "notification_delivery_failed",
            {
                "channel": channel,
                "reason": reason,
                "samples": samples,
                "failures": failures,
                "consecutive": host.delivery_health.consecutive(channel)
                if host.delivery_health
                else 0,
            },
            bypass_aggregation=True,
            target_channels=targets,
        )
    except Exception as e:  # noqa: BLE001 — 告警失败不得影响正常发送链路
        logger.warning(t("notification.manager.delivery_alert_failed").format(error=e))
    finally:
        host._sending_delivery_alert = False
