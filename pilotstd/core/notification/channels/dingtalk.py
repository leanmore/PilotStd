# pilotstd/core/notification/channels/dingtalk.py
"""钉钉群机器人 Webhook 通知渠道。"""

import base64
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..channel import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)


class DingTalkChannel(NotificationChannel):
    """钉钉群机器人 Webhook。支持加签（secret）。"""

    def __init__(self, webhook_url: str, secret: str = ""):
        self._url = webhook_url
        self._secret = secret  # 加签密钥，空字符串表示不加签

    def _sign(self) -> str:
        """钉钉加签：timestamp + secret → HMAC-SHA256 → Base64 → URL encode。"""
        # 无 secret 时不加签，直接返回空字符串
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
        # URL encode 签名：钉钉要求对 Base64 结果进行 URL 编码
        sign = quote(base64.b64encode(hmac_code).decode("utf-8"))
        return f"&timestamp={timestamp}&sign={sign}"

    def send(self, message: NotificationMessage) -> bool:
        """发送 markdown 格式通知到钉钉群。"""
        if not self._url:
            logger.warning("钉钉通知 URL 为空")
            return False

        try:
            # 拼接加签参数到 URL
            url = self._url + self._sign()
            text = f"## {message.title}\n{message.body}"
            if message.standard_number:
                text += f"\n\n> 标准号: {message.standard_number}"

            payload = json.dumps(
                {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": message.title[:50],  # 钉钉标题上限 50 字符
                        "text": text,
                    },
                }
            ).encode("utf-8")

            req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning("钉钉通知 HTTP %d", resp.status)
                    return False
                data = json.loads(resp.read().decode("utf-8"))
                # 钉钉返回 errcode=0 表示成功
                if data.get("errcode") == 0:
                    return True
                logger.warning("钉钉通知失败: %s", data.get("errmsg", "未知错误"))
                return False
        except Exception as e:
            logger.warning("钉钉通知异常: %s", e)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        """钉钉配置只需 webhook_url。secret 可选。"""
        return bool(config.get("webhook_url"))
