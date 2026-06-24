# pilotstd/core/notification/channels/feishu.py
"""飞书机器人 Webhook 通知渠道。"""

import json
import logging
from urllib.request import Request, urlopen

from ..channel import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书机器人 Webhook。"""

    def __init__(self, webhook_url: str):
        self._url = webhook_url

    def send(self, message: NotificationMessage) -> bool:
        if not self._url:
            return False
        try:
            color_map = {"info": "green", "warning": "yellow", "error": "red"}
            color = color_map.get(message.level, "green")
            content = [
                [
                    {"tag": "text", "text": message.body},
                ]
            ]
            if message.standard_number:
                content.append([{"tag": "text", "text": f"标准号: {message.standard_number}"}])
            payload = json.dumps(
                {
                    "msg_type": "interactive",
                    "card": {
                        "header": {
                            "title": {"tag": "plain_text", "content": message.title},
                            "template": color,
                        },
                        "elements": [
                            {"tag": "markdown", "content": message.body},
                        ],
                    },
                }
            ).encode("utf-8")
            req = Request(self._url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    if data.get("code") == 0:
                        return True
                    logger.warning("飞书通知失败: %s", data.get("msg", ""))
                    return False
                return False
        except Exception as e:
            logger.warning("飞书通知异常: %s", e)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        return bool(config.get("webhook_url"))
