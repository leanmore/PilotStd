# 模块：项目/核心//渠道/脚本
"""企业微信机器人 Webhook 通知渠道。"""

import json
import logging
from typing import Any
from urllib.request import Request, urlopen

from ..channel import NotificationMessage
from ..renderer import MarkdownRenderer
from .base import NotificationChannel

logger = logging.getLogger(__name__)


class WechatChannel(NotificationChannel):
    """企业微信机器人 Webhook。支持 text 和 markdown 类型。"""

    def __init__(self, webhook_url: str):
        self._url = webhook_url
        self._renderer = MarkdownRenderer()
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    def send(self, message: NotificationMessage) -> bool:
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._url:
            self.last_error = "渠道未配置 webhook_url"
            return False
        try:
            # 使用渲染消息体
            rendered = self._renderer.render(message)
            # 标准号以引用块形式追加
            if message.standard_number:
                rendered += f"\n> 标准号: {message.standard_number}"
            payload = json.dumps(
                {
                    "msgtype": "markdown",
                    "markdown": {"content": rendered},
                }
            ).encode("utf-8")
            req = Request(self._url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                self.last_error = f"企业微信 HTTP {resp.status}"
                logger.warning("企业微信通知失败: HTTP %d", resp.status)
                return False
        except Exception as e:
            # 读取错误响应体用于诊断（回调返回非 200 时的具体错误）
            body = ""
            from urllib.error import HTTPError

            if isinstance(e, HTTPError):
                try:
                    body = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
            # 透传具体错误描述
            self.last_error = f"{e}: {body}" if body else str(e)
            logger.warning("企业微信通知异常: %s, body=%s", e, body)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        return bool(config.get("webhook_url"))

    # ── v1.1 R2 渠道契约（继承自 channels.base.NotificationChannel） ──

    @property
    def name(self) -> str:
        """渠道唯一标识。"""
        return "wechat"

    def test(self) -> bool:
        """发送一条测试消息验证渠道连通性。"""
        return self.send(NotificationMessage(title="PilotStd Test", body="Channel connectivity test"))

    def get_config_schema(self) -> dict[str, Any]:
        """渠道配置字段 schema（供前端动态渲染配置表单）。"""
        return {
            "webhook_url": {"type": "string", "label": "Webhook 地址", "required": True, "secret": False},
        }
