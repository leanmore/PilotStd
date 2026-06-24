# pilotstd/core/notification/channels/wechat.py
"""企业微信机器人 Webhook 通知渠道。"""

import json
import logging
from urllib.request import Request, urlopen

from ..channel import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)


class WechatChannel(NotificationChannel):
    """企业微信机器人 Webhook。支持 text 和 markdown 类型。"""

    def __init__(self, webhook_url: str):
        self._url = webhook_url

    def send(self, message: NotificationMessage) -> bool:
        if not self._url:
            return False
        try:
            # markdown 格式：标题加粗 + 正文
            md_content = f"## {message.title}\n{message.body}"
            if message.standard_number:
                md_content += f"\n> 标准号: {message.standard_number}"
            payload = json.dumps(
                {
                    "msgtype": "markdown",
                    "markdown": {"content": md_content},
                }
            ).encode("utf-8")
            req = Request(self._url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                logger.warning("企业微信通知失败: HTTP %d", resp.status)
                return False
        except Exception as e:
            logger.warning("企业微信通知异常: %s", e)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        return bool(config.get("webhook_url"))
