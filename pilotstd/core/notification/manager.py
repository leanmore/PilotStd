# 模块：项目/核心//管理器脚本
"""NotificationManager——多渠道通知分发与日志记录。"""
# 交互契约：_()统一入口（策略表→渠道路由→聚合器→发送）；聚合器默认5窗口合并同类事件，
# _事件实时发送（系统异常须及时感知）；静音时段暂存队列表定时补发；
# 日志与渠道发送在同一块（避免"发送成功但无日志"的审计盲区）

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Optional, cast

from pilotstd.i18n import t

from ..db import Database
from ._credentials import CredentialHelper
from ._format_utils import do_test_send, format_standard_status_changed_aggregated
from ._manager_ops import _NotificationOpsMixin
from ._message_builders import (
    _build_announce_fetch_summary_message,
    _build_announcement_check_complete_message,
    _build_announcement_fetch_complete_message,
    _build_announcement_fetch_failed_message,
    _build_archive_abandoned_message,
    _build_archive_complete_message,
    _build_archive_failed_message,
    _build_auto_backup_message,
    _build_auto_scan_failed_message,
    _build_batch_download_complete_message,
    _build_batch_query_summary_message,
    _build_date_reminder_message,
    _build_download_complete_message,
    _build_download_failed_message,
    _build_download_started_message,
    _build_expire_standard_moved_message,
    _build_fallback_message,
    _build_favorite_created_message,
    _build_image_update_available_message,
    _build_normalize_complete_message,
    _build_normalize_failed_message,
    _build_query_empty_message,
    _build_query_failed_message,
    _build_quota_exhausted_message,
    _build_replacement_not_found_message,
    _build_scan_complete_message,
    _build_scan_empty_message,
    _build_standard_first_registered_message,
    _build_standard_status_changed_message,
    _build_task_execution_failed_message,
    _build_trust_ip_update_message,
    _build_validity_batch_report_message,
    _build_validity_round_summary_message,
    _build_validity_standard_failed_message,
    _build_validity_system_failed_message,
    _build_worker_error_message,
)
from ._policy import NotificationPolicyHelper
from .channel import NotificationMessage
from .channels.dingtalk import DingTalkChannel
from .channels.feishu import FeishuChannel
from .channels.telegram import TelegramChannel
from .channels.wechat import WechatChannel

logger = logging.getLogger(__name__)


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    import secrets

    return secrets.token_hex(4)

_CHANNEL_CLASSES = {
    "wechat": WechatChannel,
    "telegram": TelegramChannel,
    "feishu": FeishuChannel,
    "dingtalk": DingTalkChannel,
}


class NotificationManager(_NotificationOpsMixin):
    """通知管理器。

    初始化时加载配置，按事件规则分发到各渠道，记录发送日志。
    渠道加载失败时降级（记录错误，不阻断流程）。
    """

    def __init__(self, config: Any, db: Database, user_id: int, ws_broadcast: Callable | None = None):
        self._cfg = config
        self._db = db
        self._user_id = user_id
        self._policy = NotificationPolicyHelper(db, config)
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
        self._ws_broadcast = ws_broadcast
        self._init_event_builders()
        if self._enabled:
            self._init_channels()
        # 消息聚合器（线程安全，同类事件合并为一条发送）
        self.aggregator: Optional[Any] = None
        self._aggregate_enabled = config.get("notification.aggregate_enabled", False)
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
        """从 user_credentials 表加载各渠道配置并初始化渠道实例。"""
        creds: dict[str, dict[str, str]] = {}
        if self._cred_helper:
            creds = self._cred_helper.get_all(self._user_id)
        for name, cls in _CHANNEL_CLASSES.items():
            try:
                ch_cfg = creds.get(name) or {}
                enabled = ch_cfg.get("enabled", True)
                if isinstance(enabled, str):
                    enabled = enabled.lower() not in ("false", "0", "")
                if not enabled:
                    continue
                if name == "telegram":
                    token = (ch_cfg.get("bot_token") or "").strip()
                    chat_id = (ch_cfg.get("chat_id") or "").strip()
                    if token and chat_id:
                        self._channels[name] = cls(token, chat_id)
                else:
                    url = (ch_cfg.get("webhook_url") or "").strip()
                    if not url:
                        continue
                    if name == "dingtalk":
                        secret = (ch_cfg.get("secret") or "").strip()
                        self._channels[name] = cls(url, secret)
                    elif name == "feishu":
                        secret = (ch_cfg.get("secret") or "").strip()
                        self._channels[name] = cls(url, secret)
                    else:
                        self._channels[name] = cls(url)
            except Exception as e:
                logger.warning("通知渠道 %s 初始化失败: %s", name, e)

    # ── 发送事件 ──────────────────────────────────────────────

    def send_event(self, event_type: str, event_data: dict[str, Any], bypass_aggregation: bool = False) -> None:
        """根据策略表分发通知到各渠道（经过聚合器缓冲）。

        优先从 notification_policy 表读取渠道事件订阅，
        若表为空则回退到 config.json 的 notification.rules 配置。
        bypass_aggregation=True 时跳过聚合缓冲，实时发送（供紧急告警事件使用）。
        """
        if not self._enabled:
            logger.debug("通知功能未启用，跳过事件 %s 的发送", event_type)
            return
        target_channels = self._policy.get_channels_for_event(self._user_id, event_type)
        if not target_channels:
            logger.info("事件 %s 无订阅渠道，跳过发送", event_type)
            return

        msg = self._build_message(event_type, event_data)
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
            except Exception as e:
                self._log(event_type, ch_name, msg, "failed", str(e), sent_at)
        if msg:
            self._broadcast_to_ws(event_type, msg)

    # ── 静音时段 ──────────────────────────────────────────────

    def _is_quiet_hours(self) -> bool:
        """检查当前是否在静音时段内（跨天支持 22:00-07:00）。"""
        if not self._cfg.get("notification.quiet_hours_enabled", False):
            return False
        now = datetime.now().time()
        start_str = self._cfg.get("notification.quiet_hours_start", "22:00")
        end_str = self._cfg.get("notification.quiet_hours_end", "07:00")
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
        if start <= end:
            return start <= now <= end
        else:
            return now >= start or now <= end

    def _enqueue_notification(self, msg: NotificationMessage, target_channels: list[str]) -> None:
        """静音时段内暂存通知到 notification_queue 表。"""
        end_str = self._cfg.get("notification.quiet_hours_end", "07:00")
        hour, minute = map(int, end_str.split(":"))
        now = datetime.now()
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= scheduled:
            scheduled += timedelta(days=1)
        event_data = json.dumps(
            {
                "event_type": msg.event_type,
                "title": msg.title,
                "body": msg.body,
                "level": msg.level,
                "link": msg.link,
                "icon": msg.icon,
                "channels": target_channels,
            },
            ensure_ascii=False,
        )
        self._db.execute(
            "INSERT INTO notification_queue (event_type, event_data, status, scheduled_time, created_at) "
            "VALUES (?, ?, 'suppressed', ?, ?)",
            (msg.event_type, event_data, scheduled.isoformat(), now.isoformat()),
        )
        logger.info("通知 %s 在静音时段内，已暂存，计划 %s 补发", msg.event_type, scheduled.isoformat())

    def release_suppressed_notifications(self) -> int:
        """补发所有已到期的压制通知，返回补发条数。"""
        now = datetime.now().isoformat()
        rows = self._db.fetchall(
            "SELECT id, event_type, event_data FROM notification_queue "
            "WHERE status='suppressed' AND scheduled_time <= ?",
            (now,),
        )
        if not rows:
            return 0
        for row in rows:
            self._db.execute("UPDATE notification_queue SET status='sending' WHERE id=?", (row["id"],))
            try:
                data = json.loads(row["event_data"])
                channels = data.pop("channels", [])
                msg = NotificationMessage(
                    **{k: v for k, v in data.items() if k in ("title", "body", "level", "link", "icon", "event_type")}
                )
                self._send_now(msg, channels)
                self._db.execute("UPDATE notification_queue SET status='sent' WHERE id=?", (row["id"],))
            except Exception as e:
                logger.error("补发通知失败: %s", e)
                self._db.execute(
                    "UPDATE notification_queue SET status='failed', error_msg=? WHERE id=?",
                    (str(e), row["id"]),
                )
        return len(rows)

    def shutdown(self) -> None:
        """优雅关闭：刷新聚合器中所有缓冲消息（防止丢失）。"""
        if self.aggregator is not None:
            self.aggregator.shutdown()

    def _init_event_builders(self) -> None:
        """初始化事件类型 → 消息构建函数的映射表。"""
        self._EVENT_BUILDERS = {
            "archive_complete": _build_archive_complete_message,
            "standard_status_changed": _build_standard_status_changed_message,
            "standard_first_registered": _build_standard_first_registered_message,
            "announcement_fetch_complete": _build_announcement_fetch_complete_message,
            "announce_fetch_summary": _build_announce_fetch_summary_message,
            "auto_backup": _build_auto_backup_message,
            "announcement_check_complete": _build_announcement_check_complete_message,
            "batch_download_complete": _build_batch_download_complete_message,
            "auto_scan_failed": _build_auto_scan_failed_message,
            "validity_batch_report": _build_validity_batch_report_message,
            "validity_round_summary": _build_validity_round_summary_message,
            "validity_standard_failed": _build_validity_standard_failed_message,
            "validity_system_failed": _build_validity_system_failed_message,
            "image_update_available": _build_image_update_available_message,
            "batch_query_summary": _build_batch_query_summary_message,
            "trust_ip_update": _build_trust_ip_update_message,
            "worker_error": _build_worker_error_message,
            "download_failed": _build_download_failed_message,
            "archive_abandoned": _build_archive_abandoned_message,
            "favorite_created": _build_favorite_created_message,
            "download_started": _build_download_started_message,
            "download_complete": _build_download_complete_message,
            "normalize_complete": _build_normalize_complete_message,
            "scan_complete": _build_scan_complete_message,
            "task_execution_failed": _build_task_execution_failed_message,
            "date_reminder": _build_date_reminder_message,
            "scan_empty": _build_scan_empty_message,
            "query_failed": _build_query_failed_message,
            "query_empty": _build_query_empty_message,
            "archive_failed": _build_archive_failed_message,
            "announcement_fetch_failed": _build_announcement_fetch_failed_message,
            "normalize_failed": _build_normalize_failed_message,
            "expire_standard_moved": _build_expire_standard_moved_message,
            "replacement_not_found": _build_replacement_not_found_message,
            "quota_exhausted": _build_quota_exhausted_message,
        }

    def _build_message(self, event_type: str, data: dict) -> NotificationMessage:
        """根据事件类型查找构建器生成通知消息，找不到则用兜底构建器。"""
        builder = self._EVENT_BUILDERS.get(event_type)
        if builder is not None:
            return builder(data)
        return _build_fallback_message(event_type, data)


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
