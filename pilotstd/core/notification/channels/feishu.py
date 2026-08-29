# 模块：项目/核心//渠道/脚本
"""飞书机器人 Webhook 通知渠道。"""

import json
import logging
from typing import Any
from urllib.request import Request, urlopen

from ..channel import NotificationMessage
from ..renderer import FeishuCardRenderer
from .base import NotificationChannel

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书机器人 Webhook。"""

    def __init__(self, webhook_url: str):
        self._url = webhook_url
        self._renderer = FeishuCardRenderer()
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    def send(self, message: NotificationMessage) -> bool:
        """发送交互式卡片通知到飞书群。"""
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._url:
            self.last_error = "渠道未配置 webhook_url"
            return False
        try:
            # 使用飞书渲染卡片
            card = self._renderer.render(message)

            # 标准号在卡片底部追加为备注元素
            if message.standard_number:
                card["elements"].append({"tag": "markdown", "content": f"标准号: {message.standard_number}"})

            payload = json.dumps(
                {
                    "msg_type": "interactive",
                    "card": card,
                }
            ).encode("utf-8")
            req = Request(self._url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    # 飞书返回=0表示成功
                    if data.get("code") == 0:
                        return True
                    msg = data.get("msg", "")
                    self.last_error = f"飞书返回失败: {msg}"
                    logger.warning("飞书通知失败: %s", msg)
                    return False
                self.last_error = f"飞书 HTTP {resp.status}"
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
            logger.warning("飞书通知异常: %s, body=%s", e, body)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        """飞书配置只需 webhook_url。"""
        return bool(config.get("webhook_url"))

    # ── v1.1 R2 渠道契约（继承自 channels.base.NotificationChannel） ──

    @property
    def name(self) -> str:
        """渠道唯一标识。"""
        return "feishu"

    def test(self) -> bool:
        """发送一条测试消息验证渠道连通性。"""
        return self.send(NotificationMessage(title="PilotStd Test", body="Channel connectivity test"))

    def get_config_schema(self) -> dict[str, Any]:
        """渠道配置字段 schema（供前端动态渲染配置表单）。"""
        return {
            "webhook_url": {"type": "string", "label": "Webhook 地址", "required": True, "secret": False},
        }
