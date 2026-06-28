# pilotstd/core/notification/manager.py
"""NotificationManager——多渠道通知分发与日志记录。"""

import logging
from datetime import datetime, timezone
from typing import Any

from ..db import Database
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


class NotificationManager:
    """通知管理器。

    初始化时加载配置，按事件规则分发到各渠道，记录发送日志。
    渠道加载失败时降级（记录错误，不阻断流程）。
    """

    def __init__(self, config: Any, db: Database):
        self._cfg = config
        self._db = db
        self._enabled = config.get("notification.enabled", False)
        self._channels: dict[str, Any] = {}
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

    def _build_message(self, event_type: str, data: dict) -> NotificationMessage:
        std_no = data.get("standard_number", "")
        if event_type == "archive_complete":
            count = data.get("count", 0)
            return NotificationMessage(
                title="归档完成",
                body=f"本次归档 {count} 条标准",
                level="info",
                standard_number=std_no,
                event_type=event_type,
            )
        elif event_type == "standard_status_changed":
            old = data.get("old_status", "")
            new = data.get("new_status", "")
            return NotificationMessage(
                title="标准状态变更",
                body=f"{std_no}: {old} → {new}",
                level="warning" if new == "已废止" else "info",
                standard_number=std_no,
                event_type=event_type,
            )
        elif event_type == "standard_expired":
            return NotificationMessage(
                title="标准已废止",
                body=f"{std_no} 状态变更为已废止",
                level="error",
                standard_number=std_no,
                event_type=event_type,
            )
        elif event_type == "standard_first_registered":
            return NotificationMessage(
                title="新标准入库",
                body=f"{std_no} 首次归档入库",
                level="info",
                standard_number=std_no,
                event_type=event_type,
            )
        elif event_type == "check_batch_complete":
            count = data.get("count", 0)
            changed = data.get("changed", 0)
            return NotificationMessage(
                title="时效性检查完成",
                body=f"检查 {count} 条标准，{changed} 条状态变更",
                level="info",
                event_type=event_type,
            )
        elif event_type == "announcement_fetch_complete":
            count = data.get("count", 0)
            return NotificationMessage(
                title="公告抓取完成",
                body=f"已抓取 {count} 条新公告",
                level="info",
                event_type=event_type,
            )
        elif event_type == "auto_backup":
            success = data.get("success", False)
            if success:
                size_mb = data.get("size_mb", 0)
                return NotificationMessage(
                    title="数据库备份成功",
                    body=f"备份完成，大小 {size_mb:.2f} MB",
                    level="info",
                    event_type=event_type,
                )
            else:
                error = data.get("error", "未知错误")
                return NotificationMessage(
                    title="数据库备份失败",
                    body=f"错误：{error}",
                    level="error",
                    event_type=event_type,
                )
        else:
            return NotificationMessage(
                title=event_type,
                body=str(data),
                level="info",
                event_type=event_type,
            )

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

    # ── 查询日志 ──────────────────────────────────────────────

    def get_logs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        rows = self._db.fetchall(
            "SELECT * FROM notification_log ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(r) for r in rows]

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
