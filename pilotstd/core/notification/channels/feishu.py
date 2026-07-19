# pilotstd/core/notification/channels/feishu.py
"""飞书机器人 Webhook 通知渠道。"""

import json
import logging
from urllib.request import Request, urlopen

from ..channel import NotificationChannel, NotificationMessage
from ..renderer import FeishuCardRenderer

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书机器人 Webhook。"""

    def __init__(self, webhook_url: str):
        self._url = webhook_url
        self._renderer = FeishuCardRenderer()

    def send(self, message: NotificationMessage) -> bool:
        """发送交互式卡片通知到飞书群。"""
        if not self._url:
            return False
        try:
            # 使用 FeishuCardRenderer 渲染卡片 dict
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
