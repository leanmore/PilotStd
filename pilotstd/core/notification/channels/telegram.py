# 模块：项目/核心//渠道/脚本
"""Telegram Bot API 通知渠道。"""

import json
import logging
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ..channel import NotificationChannel, NotificationMessage
from ..renderer import TelegramRenderer

logger = logging.getLogger(__name__)

# 永久性错误去重：同一错误信息的最小日志间隔（秒）
_ERROR_DEBOUNCE_SECONDS = 120


class TelegramChannel(NotificationChannel):
    """Telegram Bot API。支持 parse_mode=MarkdownV2。"""

    def __init__(self, bot_token: str, chat_id: str):
        self._token = bot_token.strip()
        self._chat_id = chat_id.strip()
        self._renderer = TelegramRenderer()
        # 去重：记录上次错误信息及时间戳
        self._last_error_key: str = ""
        self._last_error_time: float = 0.0

    def send(self, message: NotificationMessage) -> bool:
        if not self._token or not self._chat_id:
            return False
        try:
            # 使用电报渲染2文本
            text = self._renderer.render(message)
            # 标准号以等宽格式追加
            if message.standard_number:
                text += f"\n`{self._renderer._escape(message.standard_number)}`"
            payload = json.dumps(
                {
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "MarkdownV2",
                }
            ).encode("utf-8")
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            req = Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    if data.get("ok"):
                        # 成功后清除错误去重状态
                        self._last_error_key = ""
                        self._last_error_time = 0.0
                        return True
                    logger.warning("Telegram 通知失败: %s", data.get("description", ""))
                    return False
                return False
        except HTTPError as e:
            # 404/401→配置错误（无效/已撤销），不应重试
            # 5→服务端临时故障，可重试但不在本层做
            if e.code == 404:
                self._log_dedup(
                    "Telegram 404 — bot token 无效或已撤销，请检查配置中的 bot_token。"
                    " 在修复配置之前，Telegram 通知将静默跳过。"
                )
            elif e.code == 401:
                self._log_dedup("Telegram 401 Unauthorized — bot token 鉴权失败，请重新生成 token。")
            else:
                logger.warning("Telegram HTTP %s: %s", e.code, e)
            return False
        except Exception as e:
            logger.warning("Telegram 通知异常: %s", e)
            return False

    def _log_dedup(self, msg: str) -> None:
        """去重日志：相同消息在 _ERROR_DEBOUNCE_SECONDS 内只记一次。"""
        now = time.monotonic()
        if msg == self._last_error_key and (now - self._last_error_time) < _ERROR_DEBOUNCE_SECONDS:
            return
        self._last_error_key = msg
        self._last_error_time = now
        logger.error(msg)

    @staticmethod
    def validate_config(config: dict) -> bool:
        return bool(config.get("bot_token") and config.get("chat_id"))
