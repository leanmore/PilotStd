# 模块：项目/核心//渠道/脚本
"""钉钉群机器人 Webhook 通知渠道。"""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..channel import NotificationMessage
from ..renderer import MarkdownRenderer
from .base import NotificationChannel

logger = logging.getLogger(__name__)


class DingTalkChannel(NotificationChannel):
    """钉钉群机器人 Webhook。支持加签（secret）。"""

    def __init__(self, webhook_url: str, secret: str = ""):
        self._url = webhook_url
        self._secret = secret  # 加签密钥，空字符串表示不加签
        self._renderer = MarkdownRenderer()
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""

    def _sign(self) -> str:
        """钉钉加签：timestamp + secret → HMAC-SHA256 → Base64 → URL encode。"""
        # 无时不加签，直接返回空字符串
        if not self._secret:
            return ""
        # 钉钉要求毫秒级时间戳
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        # 链接签名：钉钉要求对64结果进行链接编码
        sign = quote(base64.b64encode(hmac_code).decode("utf-8"))
        return f"&timestamp={timestamp}&sign={sign}"

    def send(self, message: NotificationMessage) -> bool:
        """发送 markdown 格式通知到钉钉群。"""
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._url:
            self.last_error = "渠道未配置 webhook_url"
            logger.warning("钉钉通知 URL 为空")
            return False

        try:
            # 拼接加签参数到链接
            url = self._url + self._sign()

            # 使用渲染消息体
            rendered = self._renderer.render(message)
            # 钉钉需要标准号以引用块形式追加
            if message.standard_number:
                rendered += f"\n\n> 标准号: {message.standard_number}"

            payload = json.dumps(
                {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": message.title[:50],  # 钉钉标题上限 50 字符
                        "text": rendered,
                    },
                }
            ).encode("utf-8")

            req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    self.last_error = f"钉钉 HTTP {resp.status}"
                    logger.warning("钉钉通知 HTTP %d", resp.status)
                    return False
                data = json.loads(resp.read().decode("utf-8"))
                # 钉钉返回=0表示成功
                if data.get("errcode") == 0:
                    return True
                errmsg = data.get("errmsg", "未知错误")
                self.last_error = f"钉钉返回失败: {errmsg}"
                logger.warning("钉钉通知失败: %s", errmsg)
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
            logger.warning("钉钉通知异常: %s, body=%s", e, body)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        """钉钉配置只需 webhook_url。secret 可选。"""
        return bool(config.get("webhook_url"))

    # ── v1.1 R2 渠道契约（继承自 channels.base.NotificationChannel） ──

    @property
    def name(self) -> str:
        """渠道唯一标识。"""
        return "dingtalk"

    def test(self) -> bool:
        """发送一条测试消息验证渠道连通性。"""
        return self.send(NotificationMessage(title="PilotStd Test", body="Channel connectivity test"))

    def get_config_schema(self) -> dict[str, Any]:
        """渠道配置字段 schema（供前端动态渲染配置表单）。"""
        return {
            "webhook_url": {"type": "string", "label": "Webhook 地址", "required": True, "secret": False},
            "secret": {"type": "string", "label": "加签密钥", "required": False, "secret": True},
        }
