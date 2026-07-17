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
        """发送交互式卡片通知到飞书群。"""
        if not self._url:
            return False
        try:
            # 消息级别映射为飞书卡片 header 颜色
            color_map = {"info": "green", "warning": "yellow", "error": "red"}
            color = color_map.get(message.level, "green")
            # 飞书交互式卡片格式：header + markdown 正文
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
                    # 飞书返回 code=0 表示成功
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
        """飞书配置只需 webhook_url。"""
        return bool(config.get("webhook_url"))
