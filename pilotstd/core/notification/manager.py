# pilotstd/core/notification/manager.py
"""NotificationManager——多渠道通知分发与日志记录。"""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import Database
from ._message_builders import MessageBuildersMixin
from .channel import NotificationMessage
from .channels.dingtalk import DingTalkChannel
from .channels.feishu import FeishuChannel
from .channels.telegram import TelegramChannel
from .channels.wechat import WechatChannel

logger = logging.getLogger(__name__)

_CHANNEL_CLASSES = {
    "wechat": WechatChannel,
    "telegram": TelegramChannel,
    "feishu": FeishuChannel,
    "dingtalk": DingTalkChannel,
}


class NotificationManager(MessageBuildersMixin):
    """通知管理器。

    初始化时加载配置，按事件规则分发到各渠道，记录发送日志。
    渠道加载失败时降级（记录错误，不阻断流程）。
    """

    def __init__(self, config: Any, db: Database, ws_broadcast: Callable | None = None):
        self._cfg = config
        self._db = db
        self._enabled = config.get("notification.enabled", False)
        self._channels: dict[str, Any] = {}
        self._ws_broadcast = ws_broadcast
        self._init_event_builders()
        if self._enabled:
            self._init_channels()
        # 服务端聚合开关
        self._aggregate_enabled = config.get("notification.aggregate_window_seconds", 0) > 0
        if self._aggregate_enabled:
            from .aggregate_buffer import AggregateBuffer

            window = float(config.get("notification.aggregate_window_seconds", 30))
            max_events = int(config.get("notification.aggregate_max_events", 50))
            self.buffer = AggregateBuffer(window, max_events, self._do_send_merged)

    def _init_channels(self) -> None:
        for name, cls in _CHANNEL_CLASSES.items():
            try:
                if not self._cfg.get(f"notification.channels.{name}.enabled", False):
                    continue
                if name == "telegram":
                    token = self._cfg.get("notification.channels.telegram.bot_token", "")
                    chat_id = self._cfg.get("notification.channels.telegram.chat_id", "")
                    if token and chat_id:
                        self._channels[name] = cls(token, chat_id)
                else:
                    url = self._cfg.get(f"notification.channels.{name}.webhook_url", "")
                    if not url:
                        continue
                    if name == "dingtalk":
                        secret = self._cfg.get(f"notification.channels.{name}.secret", "")
                        self._channels[name] = cls(url, secret)
                    else:
                        self._channels[name] = cls(url)
            except Exception as e:
                logger.warning("通知渠道 %s 初始化失败: %s", name, e)

    # ── 发送事件 ──────────────────────────────────────────────

    def send_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """根据 rules 映射分发通知到各渠道。"""
        if not self._enabled:
            return
        rules = self._cfg.get(f"notification.rules.{event_type}")
        if not rules:
            return
        if isinstance(rules, str):
            target_channels = [c.strip() for c in rules.split(",") if c.strip()]
        else:
            target_channels = rules

        msg = self._build_message(event_type, event_data)
        if self._aggregate_enabled:
            # 聚合模式：事件进入缓冲，由 AggregateBuffer 定时合并后回调 _do_send_merged
            import asyncio

            try:
                asyncio.create_task(self.buffer.add_event(event_type, msg))
            except RuntimeError:
                # 不在 async 上下文中（如 CLI 直接调用），降级为直发
                self._do_send(msg, target_channels)
        else:
            self._do_send(msg, target_channels)

    def _do_send(self, msg: NotificationMessage, target_channels: list[str]) -> None:
        """逐渠道发送 + 写日志 + WS 广播（单条或聚合后调用）。"""
        # 静音时段检查：暂存后补发
        if self._is_quiet_hours():
            self._enqueue_notification(msg, target_channels)
            return
        self._send_now(msg, target_channels)

    def _send_now(self, msg: NotificationMessage, target_channels: list[str]) -> None:
        """实际执行发送（写日志 + 渠道推送 + WS 广播）。"""
        event_type = msg.event_type
        for ch_name in target_channels:
            channel = self._channels.get(ch_name)
            sent_at = datetime.now(timezone.utc).isoformat()
            if channel is None:
                self._log(event_type, ch_name, msg, "failed", f"渠道 {ch_name} 未启用或初始化失败", sent_at)
                continue
            try:
                ok = channel.send(msg)
                self._log(event_type, ch_name, msg, "success" if ok else "failed", "" if ok else "发送失败", sent_at)
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

    def _do_send_merged(self, msg: NotificationMessage) -> None:
        """聚合后回调：提取渠道并转发到 _do_send。"""
        rules = self._cfg.get(f"notification.rules.{msg.event_type}")
        if not rules:
            return
        if isinstance(rules, str):
            target_channels = [c.strip() for c in rules.split(",") if c.strip()]
        else:
            target_channels = rules
        self._do_send(msg, target_channels)

    def _init_event_builders(self) -> None:
        """初始化事件构建器映射表"""
        self._EVENT_BUILDERS = {
            "archive_complete": self._build_archive_complete_message,
            "standard_status_changed": self._build_standard_status_changed_message,
            "standard_expired": self._build_standard_expired_message,
            "standard_first_registered": self._build_standard_first_registered_message,
            "announcement_fetch_complete": self._build_announcement_fetch_complete_message,
            "auto_backup": self._build_auto_backup_message,
            "announcement_check_complete": self._build_announcement_check_complete_message,
            "batch_download_complete": self._build_batch_download_complete_message,
            "auto_scan_failed": self._build_auto_scan_failed_message,
            "validity_batch_report": self._build_validity_batch_report_message,
            "validity_round_summary": self._build_validity_round_summary_message,
            "validity_standard_failed": self._build_validity_standard_failed_message,
            "validity_system_failed": self._build_validity_system_failed_message,
            "image_update_available": self._build_image_update_available_message,
            "batch_query_summary": self._build_batch_query_summary_message,
            "trust_ip_update": self._build_trust_ip_update_message,
            "worker_error": self._build_worker_error_message,
        }

    def _build_message(self, event_type: str, data: dict) -> NotificationMessage:
        """根据事件类型构建通知消息（字典分发）"""
        builder = self._EVENT_BUILDERS.get(event_type)
        if builder is not None:
            return builder(data)
        return self._build_fallback_message(event_type, data)

    def _log(
        self,
        event_type: str,
        channel: str,
        msg: NotificationMessage,
        status: str,
        error_msg: str,
        sent_at: str,
    ) -> None:
        try:
            self._db.execute(
                "INSERT INTO notification_log (event_type, channel, title, body, "
                "standard_number, status, error_msg, sent_at, aggregated_count, link, icon) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_type,
                    channel,
                    msg.title,
                    msg.body,
                    msg.standard_number,
                    status,
                    error_msg,
                    sent_at,
                    msg.aggregated_count,
                    msg.link,
                    msg.icon,
                ),
            )
        except Exception as e:
            logger.warning("通知日志写入失败: %s", e)

    def _broadcast_to_ws(self, event_type: str, msg: NotificationMessage) -> None:
        """在独立线程中向 WebSocket 连接广播通知。"""
        if self._ws_broadcast is None:
            return

        import threading

        # 通过回调注入执行广播（回调内部处理 WebSocket/event loop 细节）
        threading.Thread(
            target=self._ws_broadcast,
            args=(event_type, msg.title, msg.body, msg.level, msg.link, msg.icon, msg.aggregated_count),
            daemon=True,
            name="notif-ws-broadcast",
        ).start()

    # ── 公开查询方法（替代直接访问 _db）──────────────────────

    def get_logs(
        self,
        page: int = 1,
        size: int = 20,
        channel: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        is_read: bool | None = None,
    ) -> dict[str, Any]:
        """获取通知日志列表（分页 + 筛选），供 API 层调用。"""
        db = self._db
        conditions: list[str] = []
        params: list[Any] = []

        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if start_date:
            conditions.append("sent_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("sent_at <= ?")
            params.append(end_date)
        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(1 if is_read else 0)

        where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        offset = (page - 1) * size

        total_row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM notification_log {where_sql}", tuple(params))
        rows = db.fetchall(
            f"SELECT * FROM notification_log {where_sql} ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            tuple(params + [size, offset]),
        )
        return {
            "items": rows,
            "total": total_row["cnt"] if total_row else 0,
            "page": page,
            "size": size,
        }

    def mark_logs_read(self, ids: list[int] | None = None) -> int:
        """标记通知日志为已读（单条或全部），供 API 层调用。"""
        db = self._db
        if ids:
            for i in ids:
                db.execute("UPDATE notification_log SET is_read = 1 WHERE id = ?", (i,))
            return len(ids)
        else:
            db.execute("UPDATE notification_log SET is_read = 1")
            return 0

    def get_unread_count(self) -> int:
        """获取未读通知数量。"""
        row = self._db.fetchone("SELECT COUNT(*) AS cnt FROM notification_log WHERE is_read = 0")
        return row["cnt"] if row else 0

    # ── 日志清理 ──────────────────────────────────────────────

    def cleanup_logs(self, days: int = 30) -> int:
        """删除 days 天前的通知日志，返回删除条数。"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
        cur = self._db.execute("DELETE FROM notification_log WHERE sent_at < ?", (cutoff,))
        deleted = cur.rowcount
        if deleted > 0:
            logger.info("清理了 %d 条过期通知日志（保留 %d 天）", deleted, days)
        return deleted

    # ── 测试发送 ──────────────────────────────────────────────

    def test_send(
        self,
        channel: str,
        message: NotificationMessage,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """测试发送到指定渠道。params 可覆盖配置中的渠道参数（如临时 webhook_url）。"""
        override = params or {}
        ch = self._channels.get(channel)
        if ch is None:
            # 尝试实时初始化（优先使用 params 中的参数）
            cls = _CHANNEL_CLASSES.get(channel)
            if cls is None:
                return {"ok": False, "error": f"未知渠道: {channel}"}
            try:
                if channel == "telegram":
                    token = override.get("bot_token") or self._cfg.get("notification.channels.telegram.bot_token", "")
                    chat_id = override.get("chat_id") or self._cfg.get("notification.channels.telegram.chat_id", "")
                    if not token:
                        return {"ok": False, "error": "缺少 bot_token"}
                    if not chat_id:
                        return {"ok": False, "error": "缺少 chat_id"}
                    ch = cls(token, chat_id)
                elif channel == "dingtalk":
                    url = override.get("webhook_url") or self._cfg.get("notification.channels.dingtalk.webhook_url", "")
                    secret = override.get("secret") or self._cfg.get("notification.channels.dingtalk.secret", "")
                    if not url:
                        return {"ok": False, "error": "缺少 webhook_url（钉钉群机器人必填）"}
                    ch = cls(url, secret)
                elif channel == "feishu":
                    url = override.get("webhook_url") or self._cfg.get("notification.channels.feishu.webhook_url", "")
                    secret = override.get("secret") or self._cfg.get("notification.channels.feishu.secret", "")
                    if not url:
                        return {"ok": False, "error": "缺少 webhook_url（飞书机器人必填）"}
                    ch = cls(url, secret)
                elif channel == "wechat":
                    # 企业微信：优先应用消息 (corpid+agentid+corpsecret)，其次群机器人 (webhook_url)
                    corpid = override.get("corpid") or self._cfg.get("notification.channels.wechat.corpid", "")
                    agentid = override.get("agentid") or self._cfg.get("notification.channels.wechat.agentid", "")
                    corpsecret = override.get("corpsecret") or self._cfg.get(
                        "notification.channels.wechat.corpsecret", ""
                    )
                    if corpid and agentid and corpsecret:
                        # 应用消息模式 — 需特殊初始化
                        ch = cls(corpid, agentid, corpsecret)
                    else:
                        url = override.get("webhook_url") or self._cfg.get(
                            "notification.channels.wechat.webhook_url", ""
                        )
                        if not url:
                            return {
                                "ok": False,
                                "error": "缺少 webhook_url（群机器人）或 corpid+agentid+corpsecret（应用消息）",
                            }
                        ch = cls(url)
                else:
                    url = override.get("webhook_url") or self._cfg.get(
                        f"notification.channels.{channel}.webhook_url", ""
                    )
                    if not url:
                        return {"ok": False, "error": f"缺少 {channel} 渠道的 webhook_url"}
                    ch = cls(url)
            except Exception as e:
                return {"ok": False, "error": f"渠道初始化失败: {e}"}
        try:
            ok = ch.send(message)
            return {"ok": ok, "error": "" if ok else "发送失败"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
