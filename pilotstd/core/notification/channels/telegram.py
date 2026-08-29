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


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    import secrets

    return secrets.token_hex(4)


class TelegramChannel(NotificationChannel):
    """Telegram Bot API。支持 parse_mode=MarkdownV2。"""

    def __init__(self, bot_token: str, chat_id: str):
        self._token = bot_token.strip()
        self._chat_id = chat_id.strip()
        self._renderer = TelegramRenderer()
        # 错误详情透传给管理层（发送日志记录使用）
        self.last_error: str = ""
        # 去重：记录上次错误信息及时间戳
        self._last_error_key: str = ""
        self._last_error_time: float = 0.0

    def send(self, message: NotificationMessage) -> bool:
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._token or not self._chat_id:
            self.last_error = "渠道未配置 bot_token 或 chat_id"
            return False
        try:
            # 使用电报渲染2文本
            # 标准号已由构建器渲染进正文（批次2 尾部重复行消除），发送层不再追加
            text = self._renderer.render(message)
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
                    desc = data.get("description", "")
                    self.last_error = f"Telegram 返回失败: {desc}"
                    logger.warning("Telegram 通知失败: %s", desc)
                    return False
                self.last_error = f"Telegram HTTP {resp.status}"
                return False
        except HTTPError as e:
            # 读取响应体（含说明字段）用于诊断 4xx 具体原因
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                # P1-4 修复：响应体读取失败需带结构化上下文记录，禁止静默吞错
                logger.warning(
                    "Telegram 响应体读取失败: trace_id=%s source_type=telegram_channel target_chat_id=%s code=%s",
                    _log_trace_id(),
                    self._chat_id,
                    e.code,
                    exc_info=True,
                )
            # 提取具体错误描述透传（优先取 JSON 中的说明字段）
            try:
                desc = json.loads(body).get("description", body) if body else str(e)
            except Exception:
                # P1-4 修复：描述解析失败需记录，禁止静默吞错
                logger.warning(
                    "Telegram 错误描述解析失败: trace_id=%s source_type=telegram_channel "
                    "target_chat_id=%s code=%s body=%s",
                    _log_trace_id(),
                    self._chat_id,
                    e.code,
                    body[:100],
                    exc_info=True,
                )
                desc = body or str(e)
            self.last_error = f"HTTP {e.code}: {desc}"
            logger.warning("Telegram send failed: HTTP %s, body=%s", e.code, body)
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
            self.last_error = f"Telegram 发送异常: {e}"
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
