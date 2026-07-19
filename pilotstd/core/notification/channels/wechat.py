# pilotstd/core/notification/channels/wechat.py
"""企业微信机器人 Webhook 通知渠道。"""

import json
import logging
from urllib.request import Request, urlopen

from ..channel import NotificationChannel, NotificationMessage
from ..renderer import MarkdownRenderer

logger = logging.getLogger(__name__)


class WechatChannel(NotificationChannel):
    """企业微信机器人 Webhook。支持 text 和 markdown 类型。"""

    def __init__(self, webhook_url: str):
        self._url = webhook_url
        self._renderer = MarkdownRenderer()

    def send(self, message: NotificationMessage) -> bool:
        if not self._url:
            return False
        try:
            # 使用 MarkdownRenderer 渲染消息体
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
                logger.warning("企业微信通知失败: HTTP %d", resp.status)
                return False
        except Exception as e:
            logger.warning("企业微信通知异常: %s", e)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        return bool(config.get("webhook_url"))
