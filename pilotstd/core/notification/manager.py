# 模块：项目/核心//管理器脚本
"""NotificationManager——多渠道通知分发与日志记录。"""
# 交互契约：send_event 统一入口（策略表→渠道路由→聚合器→发送）；静音时段暂存队列表定时补发；
# 日志与渠道发送在同一块（避免"发送成功但无日志"的审计盲区）

import json
import logging
from datetime import datetime
from typing import Any, Optional, cast

from pilotstd.i18n import t

from ..db import Database
from . import _suppression_queue
from ._credentials import CredentialHelper
from ._format_utils import do_test_send, format_standard_status_changed_aggregated
from ._manager_ops import NotificationOps
from ._message_builders import _build_fallback_message
from ._policy import NotificationPolicyHelper
from .channel import NotificationMessage
from .channel_spec import CHANNEL_SPECS, channel_class
from .delivery_health import NotificationDeliveryHealth
from .event_spec import EVENT_SPECS

logger = logging.getLogger(__name__)


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    import secrets

    return secrets.token_hex(4)

_CHANNEL_CLASSES: dict[str, Any] = {s.name: channel_class(s) for s in CHANNEL_SPECS}

# notification_queue.event_data ⇄ NotificationMessage 的**字段契约**（唯一数据源）。
# 写入侧（_enqueue_notification）与重建侧（release_suppressed_notifications）共用本常量：
# 两侧各写一份字面量的历史写法一旦漂移，新字段就会在补发路径被静默丢弃
# （只在静音时段暴露）。新增 NotificationMessage 字段时必须同批加进这里
# ——契约由 tests/test_notification_manager.py::TestSuppressedQueueFieldRoundTrip 锁定。
# 补发白名单（唯一数据源）随静音链路移至 `_suppression_queue`；此处**再导出**，
# 保持 `from pilotstd.core.notification.manager import _QUEUE_MESSAGE_FIELDS` 的既有用法可用。
_QUEUE_MESSAGE_FIELDS = _suppression_queue._QUEUE_MESSAGE_FIELDS


class NotificationManager:
    """通知管理器。

    初始化时加载配置，按事件规则分发到各渠道，记录发送日志。
    渠道加载失败时降级（记录错误，不阻断流程）。
    """

    def __init__(self, config: Any, db: Database, user_id: int):
        self._cfg = config
        self._db = db
        self._user_id = user_id
        self._policy = NotificationPolicyHelper(db, config)
        # 静音暂存/补发：组合式注入（发送实现走 lambda ⇒ 每次补发再取 self._send_now，
        # 保证测试里替换 `mgr._send_now` 仍然生效）
        self._queue = _suppression_queue.SuppressionQueue(
            config, db, lambda msg, channels: self._send_now(msg, channels)
        )
        self._cred_helper: CredentialHelper | None = None
        try:
            config_dir = __import__("os").path.dirname(config._filepath)
            self._cred_helper = CredentialHelper(db, config_dir)
            # P2-3 (O-4)：显式迁移——首次启动从 config.json 引导凭证到 DB（幂等 + 并发安全）
            # 必须放在 _init_channels 之前，确保渠道初始化读到 DB 凭证
            self._cred_helper.migrate_from_config_if_empty(self._user_id)
        except Exception:
            # P1-2 修复：初始化失败必须带结构化上下文记录，禁止静默吞错
            # （失败后 _cred_helper 保持 None，事件路径将按"渠道未初始化"降级）
            logger.error(
                "凭据助手初始化失败: trace_id=%s source_type=credential_helper target_chat_id=-",
                _log_trace_id(),
                exc_info=True,
            )
        self._enabled = config.get("notification.enabled", False)
        # 用户级配置优先：user_preferences 表（数据库）覆盖 config.json，保证 Web 端设置实际生效
        db_enabled = self._read_user_enabled()
        if db_enabled is not None:
            self._enabled = db_enabled
        self._channels: dict[str, Any] = {}
        # 日志/查询/清理（组合式，见 _manager_ops.NotificationOps）
        self.ops = NotificationOps(self)
        self._init_event_builders()
        if self._enabled:
            self._init_channels()
        # 消息聚合器（线程安全，同类事件按「事件类型 × 关联实体」合并为一条发送）
        self.aggregator: Optional[Any] = None
        # 回退值与 defaults.py 的 `notification.aggregate_enabled=True` 对齐（第 3 批修正）：
        # 原先回退 False，会让"配置里缺该键"的旧配置文件静默关闭聚合，与 events.py
        # 文档「所有事件均经聚合器」以及 defaults 声明互相矛盾。窗口/批量两处
        # 回退值同样取自 defaults（5 秒 / 50 条）。
        self._aggregate_enabled = config.get("notification.aggregate_enabled", True)
        if self._aggregate_enabled:
            from .aggregate_buffer import NotificationAggregator
            from .events import BYPASS_EVENTS

            window = float(config.get("notification.aggregate_window_seconds", 5))
            max_events = int(config.get("notification.aggregate_max_events", 50))
            bypass_raw = config.get("notification.aggregate_bypass_events")
            bypass_events = set(bypass_raw) if bypass_raw is not None else set(BYPASS_EVENTS)
            self.aggregator = NotificationAggregator(
                self._send_now,
                window_seconds=window,
                batch_size=max_events,
                bypass_events=bypass_events,
            )
            # 注册事件特定聚合格式化器
            self.aggregator.register_formatter(
                "standard_status_changed",
                format_standard_status_changed_aggregated,
            )
        # 投递健康度（P0）：按渠道统计成败，越过阈值时发"通知投递失败"告警。
        # 这是"通知系统自己坏了"的唯一出口——生产实测曾有连续 7 天每天失败
        # 25~151 条而全程无人知晓（见 delivery_health 模块 docstring）。
        self.delivery_health: Optional[NotificationDeliveryHealth] = None
        # 告警投递中标志：断开"告警失败 → 再告警"的回环（见 _record_delivery）
        self._sending_delivery_alert = False
        self._delivery_health_enabled = bool(
            config.get("notification.delivery_health_enabled", True)
        )
        if self._delivery_health_enabled:
            self.delivery_health = NotificationDeliveryHealth(
                rate_threshold=float(
                    config.get("notification.delivery_health_rate_threshold", 0.5)
                ),
                min_samples=int(config.get("notification.delivery_health_min_samples", 10)),
                consecutive_threshold=int(
                    config.get("notification.delivery_health_consecutive_threshold", 5)
                ),
                window_seconds=float(
                    config.get("notification.delivery_health_window_seconds", 3600)
                ),
                alert_cooldown_seconds=float(
                    config.get("notification.delivery_health_alert_cooldown_seconds", 3600)
                ),
            )

    @property
    def enabled(self) -> bool:
        """通知功能是否启用（数据库 user_preferences 优先，config.json 兜底）。"""
        return cast(bool, self._enabled)

    def _read_user_enabled(self) -> bool | None:
        """从 user_preferences 表读取当前用户的 notification.enabled。

        返回 None 表示数据库无有效记录，调用方回退到 config.json 值。
        对非 str/bool/int/float 类型的值（如测试中的 MagicMock）一律视为无记录。
        """
        try:
            row = self._db.fetchone(
                "SELECT preference_value FROM user_preferences "
                "WHERE user_id=? AND preference_key='notification.enabled'",
                (self._user_id,),
            )
        except Exception:
            return None
        if row is None:
            return None
        try:
            value = row["preference_value"]
        except (KeyError, IndexError, TypeError):
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value.strip().lower() not in ("false", "0", "")
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return None

    def _init_channels(self) -> None:
        """从 user_credentials 表加载各渠道配置并初始化渠道实例。

        构造形态由 `channel_spec` 声明驱动（`ctor` 为按序传入的凭证字段，
        `ctor_required` 为构造前必须非空的字段）——新增渠道无需改本方法。
        """
        creds: dict[str, dict[str, str]] = {}
        if self._cred_helper:
            creds = self._cred_helper.get_all(self._user_id)
        for spec in CHANNEL_SPECS:
            try:
                ch_cfg = creds.get(spec.name) or {}
                enabled = ch_cfg.get("enabled", True)
                if isinstance(enabled, str):
                    enabled = enabled.lower() not in ("false", "0", "")
                if not enabled:
                    continue
                args = tuple((ch_cfg.get(f) or "").strip() for f in spec.ctor)
                guards = tuple((ch_cfg.get(f) or "").strip() for f in spec.ctor_required)
                if not all(guards):
                    continue
                self._channels[spec.name] = _CHANNEL_CLASSES[spec.name](*args)
            except Exception as e:
                logger.warning("通知渠道 %s 初始化失败: %s", spec.name, e)

    # ── 发送事件 ──────────────────────────────────────────────

    def send_event(
        self,
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
        if not self._enabled:
            logger.debug("通知功能未启用，跳过事件 %s 的发送", event_type)
            return
        if target_channels is None:
            target_channels = self._policy.get_channels_for_event(self._user_id, event_type)
        if not target_channels:
            logger.info("事件 %s 无订阅渠道，跳过发送", event_type)
            return

        msg = self._build_message(event_type, event_data)
        # 三层模型投影回填（阶段 2b-接入）：默认 stage=1 → 不生效，行为零变化。
        # 实现在 _manager_ops（本文件加入该逻辑会超 G-010 的 500 阻断线）。
        self.ops.apply_mapping(msg, event_type, event_data)
        # 构建器契约校验：空消息拦截（失败仅记错误日志，不中断主业务流程）
        try:
            self._validate_message(msg, event_type)
        except ValueError as e:
            logger.error("构建器契约校验失败，事件 %s 已跳过发送: %s", event_type, e)
            return
        self._do_send(msg, target_channels, bypass_aggregation=bypass_aggregation)

    def _validate_message(self, msg: NotificationMessage, event_type: str) -> None:
        """构建器产出契约校验：确保任何路径下消息都不会为空。

        校验规则：
        - 结构块 / 正文 / 标题至少一项非空，否则抛出数值错误（表示构建器契约被破坏）；
        - 仅有结构块无正文时记录调试日志（聚合摘要依赖正文，提示开发者补全）。

        调用方（事件发送入口）捕获数值错误并记录错误日志，不向上抛——
        校验失败不得导致收藏/下载/抓取等主业务流程崩溃。
        """
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

    def _do_send(self, msg: NotificationMessage, target_channels: list[str], bypass_aggregation: bool = False) -> None:
        """逐渠道发送：静音期暂存 → 聚合器入队 → 合并后发送。"""
        if self._is_quiet_hours():
            self._enqueue_notification(msg, target_channels)
            return
        if self.aggregator is not None and not bypass_aggregation:
            # 仅做「是否聚合」的分支决策，实际聚合全部委托给 AggregateBuffer
            # （窗口累积、分组、摘要生成都在那边），管理器不重复实现合并逻辑。
            self.aggregator.enqueue(msg, target_channels, target_id=msg.target_id)
        else:
            self._send_now(msg, target_channels)

    def _send_now(self, msg: NotificationMessage, target_channels: list[str]) -> None:
        """实际执行发送（写日志 + 渠道推送 + WS 广播）。"""
        event_type = msg.event_type
        for ch_name in target_channels:
            channel = self._channels.get(ch_name)
            sent_at = datetime.now().isoformat()
            if channel is None:
                self._log(
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
                self._log(event_type, ch_name, msg, "success" if ok else "failed", err_msg, sent_at)
                self._record_delivery(ch_name, ok)
            except Exception as e:
                self._log(event_type, ch_name, msg, "failed", str(e), sent_at)
                self._record_delivery(ch_name, False)

    # ── 投递健康度告警（P0）────────────────────────────────────

    def _record_delivery(self, channel: str, ok: bool) -> None:
        """记录一次投递结果，并在越过阈值时发出"通知投递失败"告警。

        **不回环**：告警投递期间置 `_sending_delivery_alert`，期间的结果**不再计入健康度**
        （否则告警失败又触发新告警，无限递归）。见 `_send_delivery_alert`。
        """
        if self.delivery_health is None or self._sending_delivery_alert:
            return
        self.delivery_health.record(channel, ok)
        if ok:
            return
        verdict = self.delivery_health.evaluate(channel)
        if verdict is None:
            return
        reason, samples, failures = verdict
        self._send_delivery_alert(channel, reason, samples, failures)

    def _send_delivery_alert(
        self, channel: str, reason: str, samples: int, failures: int
    ) -> None:
        """投递"通知投递失败"告警。

        目标渠道：**除故障渠道外的所有已启用渠道**——故障渠道很可能是问题本身，
        优先走旁路。若无旁路可用，仍投向故障渠道（可能也失败，但会在通知日志
        留下"曾试图告警"的痕迹，好过完全静默）。

        `bypass_aggregation=True`：告警不能等 5 秒聚合窗口（也可能被静默时段压后），
        与安全告警同理——"通知已经坏了"这件事需要立刻说出来。
        """
        self._sending_delivery_alert = True
        try:
            targets = [c for c in self._channels if c != channel] or [channel]
            self.send_event(
                "notification_delivery_failed",
                {
                    "channel": channel,
                    "reason": reason,
                    "samples": samples,
                    "failures": failures,
                    "consecutive": self.delivery_health.consecutive(channel)
                    if self.delivery_health
                    else 0,
                },
                bypass_aggregation=True,
                target_channels=targets,
            )
        except Exception as e:  # noqa: BLE001 — 告警失败不得影响正常发送链路
            logger.warning("通知投递失败告警发送异常: %s", e)
        finally:
            self._sending_delivery_alert = False

    # ── 静音时段 ──────────────────────────────────────────────

    def _is_quiet_hours(self) -> bool:
        """检查当前是否在静音时段内（实现见 `_suppression_queue`）。"""
        return self._queue.is_quiet_hours()

    def _enqueue_notification(self, msg: NotificationMessage, target_channels: list[str]) -> None:
        """静音时段内暂存通知到 notification_queue 表（实现见 `_suppression_queue`）。

        日志文案留在本模块：新模块受 G-047"零中文硬编码"约束，故它只返回计划补发时刻。
        """
        scheduled = self._queue.enqueue(msg, target_channels)
        logger.info("通知 %s 在静音时段内，已暂存，计划 %s 补发", msg.event_type, scheduled)

    def release_suppressed_notifications(self) -> int:
        """补发所有已到期的压制通知，返回补发条数（实现见 `_suppression_queue`）。"""
        count, failures = self._queue.release()
        for detail in failures:
            logger.error("补发通知失败: %s", detail)
        return count

    def shutdown(self) -> None:
        """优雅关闭：刷新聚合器中所有缓冲消息（防止丢失）。"""
        if self.aggregator is not None:
            self.aggregator.shutdown()

    def _init_event_builders(self) -> None:
        """初始化事件类型 → 消息构建函数的映射表。"""
        # 注册表由**事件规格派生**（2026-10-03 派生批次）：键 → 构建器函数；
        # 构建器位置以静态指针登记，此处经只读属性延迟解析（进程内模块首次加载后复用）。
        self._EVENT_BUILDERS = {s.key: s.builder for s in EVENT_SPECS}

    def _build_message(self, event_type: str, data: dict) -> NotificationMessage:
        """根据事件类型查找构建器生成通知消息，找不到则用兜底构建器。"""
        builder = self._EVENT_BUILDERS.get(event_type)
        if builder is not None:
            # 注册表由规格派生，取值的静态类型较宽（未定型）；用具名类型局部变量
            # 收口，避免把未定型值直接返回（不使用忽略指令或强制转换）。
            message: NotificationMessage = builder(data)
            return message
        return _build_fallback_message(event_type, data)

    # ── 日志：实现见 _manager_ops.NotificationOps，此处保留同名方法作为内部 API ──
    # 保留委托而不是让调用方直接用 self.ops：① _send_now 是内部路径，签名即契约；
    # ② tests/test_notification_combo_patch.py 用 MagicMock(spec=NotificationManager) 打桩 _log，
    #    spec 只认类属性，故 _log 必须是管理器的方法。
    # （原 _broadcast_to_ws 与之并列，随 WebSocket 死代码清理于阶段 0 删除，见
    #   docs/plans/notification-redesign/06-阶段0-1实施方案.md §1.2。）

    def _log(
        self, event_type: str, channel: str, msg: NotificationMessage, status: str, error_msg: str, sent_at: str
    ) -> None:
        """写通知发送日志（委托 NotificationOps.log）。"""
        self.ops.log(event_type, channel, msg, status, error_msg, sent_at)


    # ── 测试发送 ──────────────────────────────────────────────

    def test_send(
        self, channel: str, message: NotificationMessage, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """通过指定渠道发送测试消息，返回发送结果。"""
        return do_test_send(self, channel, message, params)

    # ── 聚合格式化器 ──────────────────────────────────────────

    def _format_standard_status_changed_aggregated(self, _event_type: str, entries: list, count: int) -> str:
        return format_standard_status_changed_aggregated(_event_type, entries, count)

    # ──策略表读写（委托_）──

    def get_policies(self, user_id: int) -> list[dict[str, Any]]:
        return self._policy.get_policies(user_id)

    def save_policy(self, user_id: int, channel: str, enabled: bool | None, events: list[str] | None) -> None:
        self._policy.save_policy(user_id, channel, enabled, events)
