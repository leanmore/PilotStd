# 模块：项目/核心//管理器脚本
"""NotificationManager——多渠道通知分发与日志记录。"""
# 交互契约：send_event 统一入口（策略表→渠道路由→聚合器→发送）；静音时段暂存队列表定时补发；
# 日志与渠道发送在同一块（避免"发送成功但无日志"的审计盲区）

import json
import logging
from typing import Any, Callable, Optional, cast

from pilotstd.i18n import t

from ..db import Database
from . import _dispatcher, _suppression_queue
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

    # 端点本地信号出口（W2 按端分流）。此处**类属性**声明不可少：
    # `tests/test_aggregate_buffer.py` 等用 `MagicMock(spec=NotificationManager)` 打桩并直接
    # 调用类方法，而 `spec` 只认类属性（与 `_log` 的同款约定）；实例侧在 `__init__` 里置 None。
    _local_sink: Callable[[NotificationMessage], None] | None = None

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
        # 端点到本地的信号出口（W2 按端分流）：桌面端注入"弹托盘气泡"，Docker 端保持 None
        # ⇒ 渠道投递不变。**与 `_enabled` 无关**：渠道开关只管"是否投递渠道"。
        self._local_sink: Callable[[NotificationMessage], None] | None = None
        # TG 接收通道（阶段 B2b-3）：默认不起线程，由 Docker lifespan 显式启动
        self._telegram_receiver: Any = None
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
        """根据策略表分发通知到各渠道（编排实现在 `_dispatcher.send_event`；签名即契约）。"""
        _dispatcher.send_event(self, event_type, event_data, bypass_aggregation, target_channels)

    def _validate_message(self, msg: NotificationMessage, event_type: str) -> None:
        """构建器产出契约校验（实现在 `_dispatcher.validate_message`）。"""
        _dispatcher.validate_message(self, msg, event_type)

    def _do_send(self, msg: NotificationMessage, target_channels: list[str], bypass_aggregation: bool = False) -> None:
        """逐渠道发送：静音暂存 → 聚合入队 → 合并发送（实现在 `_dispatcher.do_send`）。"""
        _dispatcher.do_send(self, msg, target_channels, bypass_aggregation)

    def _send_now(self, msg: NotificationMessage, target_channels: list[str]) -> None:
        """实际执行发送：写日志 + 渠道推送（实现在 `_dispatcher.send_now`）。"""
        _dispatcher.send_now(self, msg, target_channels)

    # ── 投递健康度告警（P0）────────────────────────────────────

    def _record_delivery(self, channel: str, ok: bool) -> None:
        """记录一次投递结果并在越阈时告警（实现在 `_dispatcher.record_delivery`）。"""
        _dispatcher.record_delivery(self, channel, ok)

    def _send_delivery_alert(self, channel: str, reason: str, samples: int, failures: int) -> None:
        """投递"通知投递失败"告警（实现在 `_dispatcher.send_delivery_alert`）。"""
        _dispatcher.send_delivery_alert(self, channel, reason, samples, failures)

    # ── 静音时段（实现在 _suppression_queue；此处保留同名方法作为内部 API）──────

    def set_local_sink(self, sink: Callable[[NotificationMessage], None] | None) -> None:
        """注入/清除本地信号出口（W2 按端分流）。

        Windows 端注入"托盘气泡"，让业务事件在桌面可见；Docker 端不注入（走渠道）。
        传 `None` 即关闭分流（等价于回退到"事件在本端不产生可见信号"）。
        """
        self._local_sink = sink

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

    # ── 接收通道生命周期（阶段 B2b-3）──

    def start_telegram_receiver(self) -> bool:
        """按配置启动 TG 接收通道；返回是否真的启动了长轮询线程。

        - `receive_mode=long_poll`（默认）⇒ 起守护线程主动拉取；
        - `receive_mode=webhook` ⇒ **不起线程**（由 B2b-1 的回调端点接收入站请求）；
        - 未配置 bot_token 时返回 False（能力不足，不是错误）。

        **不在 `__init__` 里自动启动**：桌面端与测试也会构造管理器，自动起线程会让
        "只发不收"的进程凭空连外网。故由 Docker 端的 lifespan 显式调用。
        """
        from .telegram_receiver import MODE_LONG_POLL, TelegramReceiver, mode_from_config

        if mode_from_config(self._cfg) != MODE_LONG_POLL:
            logger.info(t("notification.telegram.receiver_webhook_mode"))
            return False
        token = str((self._channel_credentials("telegram") or {}).get("bot_token") or "")
        if not token:
            return False
        # 局部变量显式具体类型：`self._telegram_receiver` 是 Any，直接 return 会让 mypy
        # 报 no-any-return（本项目禁止 cast/type: ignore，故用类型收窄收口）
        receiver: TelegramReceiver = self._telegram_receiver or TelegramReceiver(
            token, self._dispatch_telegram_update
        )
        self._telegram_receiver = receiver
        return receiver.start()

    def stop_telegram_receiver(self) -> None:
        """收停 TG 接收通道（可重入）。"""
        if self._telegram_receiver is not None:
            self._telegram_receiver.stop()
            self._telegram_receiver = None

    def shutdown(self) -> None:
        """进程退出前的整体收停（供 Docker lifespan 调用）。"""
        self.stop_telegram_receiver()

    def _dispatch_telegram_update(self, update: dict) -> None:
        """把一条 TG 更新交给回调服务处理（与 webhook 模式同一条授权/幂等路径）。"""
        from .callback_service import handle_callback
        from .callback_store import LogBackedReplayGuard

        raw = json.dumps(update, ensure_ascii=False).encode("utf-8")
        outcome = handle_callback(
            self._db,
            "telegram",
            {},
            raw,
            lambda user_id, channel: self._channel_credentials("telegram"),
            guard=LogBackedReplayGuard(self._db),
        )
        logger.info(
            t("notification.callback.handled").format(detail=f"long_poll status={outcome.status}")
        )

    def _channel_credentials(self, channel: str) -> dict[str, str]:
        """读当前用户该渠道的**解密**凭证（失败返回空字典）。

        `CredentialHelper` 需要 config_dir，取 `self._cfg._filepath` 的目录；取不到时用 "."。
        任何异常都吞掉并返回空字典——接收通道不能用"读不到凭证"来中断轮询。
        """
        try:
            from pathlib import Path

            from ._credentials import CredentialHelper

            filepath = getattr(self._cfg, "_filepath", "") or "."
            helper_obj = CredentialHelper(self._db, str(Path(filepath).parent))
            return helper_obj.get_channel(self._user_id, channel) or {}
        except Exception:
            logger.debug(
                t("notification.manager.credential_read_failed").format(channel=channel),
                exc_info=True,
            )
            return {}

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
