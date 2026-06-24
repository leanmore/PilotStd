# pilotstd/core/notification/channels/telegram.py
"""Telegram Bot API 通知渠道。"""

import json
import logging
from urllib.request import Request, urlopen

from ..channel import NotificationChannel, NotificationMessage

logger = logging.getLogger(__name__)


class TelegramChannel(NotificationChannel):
    """Telegram Bot API。支持 parse_mode=Markdown。"""

    def __init__(self, bot_token: str, chat_id: str):
        self._token = bot_token
        self._chat_id = chat_id

    def send(self, message: NotificationMessage) -> bool:
        if not self._token or not self._chat_id:
            return False
        try:
            text = f"*{message.title}*\n{message.body}"
            if message.standard_number:
                text += f"\n`{message.standard_number}`"
            payload = json.dumps(
                {
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                }
            ).encode("utf-8")
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            req = Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    if data.get("ok"):
                        return True
                    logger.warning("Telegram 通知失败: %s", data.get("description", ""))
                    return False
                return False
        except Exception as e:
            logger.warning("Telegram 通知异常: %s", e)
            return False

    @staticmethod
    def validate_config(config: dict) -> bool:
        return bool(config.get("bot_token") and config.get("chat_id"))
