# pilotstd/core/notification/manager.py
"""NotificationManager——多渠道通知分发与日志记录。"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
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
        # 将 rules 转为列表（配置值可能是逗号分隔字符串或列表）
        if isinstance(rules, str):
            target_channels = [c.strip() for c in rules.split(",") if c.strip()]
        else:
            target_channels = rules

        msg = self._build_message(event_type, event_data)
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

        # WebSocket 广播（独立线程，不阻塞主流程）
        if msg:
            self._broadcast_to_ws(event_type, msg)

    def _init_event_builders(self) -> None:
        """初始化事件构建器映射表"""
        self._EVENT_BUILDERS = {
            "archive_complete": self._build_archive_complete_message,
            "standard_status_changed": self._build_standard_status_changed_message,
            "standard_expired": self._build_standard_expired_message,
            "standard_first_registered": self._build_standard_first_registered_message,
            "check_batch_complete": self._build_check_batch_complete_message,
            "announcement_fetch_complete": self._build_announcement_fetch_complete_message,
            "auto_backup": self._build_auto_backup_message,
            "announcement_check_complete": self._build_announcement_check_complete_message,
            "batch_download_complete": self._build_batch_download_complete_message,
            "auto_scan_failed": self._build_auto_scan_failed_message,
            "validity_batch_report": self._build_validity_batch_report_message,
            "validity_round_summary": self._build_validity_round_summary_message,
            "validity_standard_failed": self._build_validity_standard_failed_message,
            "validity_system_failed": self._build_validity_system_failed_message,
            # 2026-07-01 新增
            "image_update_available": self._build_image_update_available_message,
            "batch_query_summary": self._build_batch_query_summary_message,
            "auto_query_complete": self._build_auto_query_complete_message,
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
                "standard_number, status, error_msg, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_type, channel, msg.title, msg.body, msg.standard_number, status, error_msg, sent_at),
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
            args=(event_type, msg.title, msg.body, msg.level),
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
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
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
