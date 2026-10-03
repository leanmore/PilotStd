# 模块：项目/核心//渠道/脚本
"""Telegram Bot API 通知渠道。"""

import json
import logging
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pilotstd.i18n import t

from ..channel import NotificationMessage
from ..renderer import TelegramRenderer
from .base import NotificationChannel

logger = logging.getLogger(__name__)

# 永久性错误去重：同一错误信息的最小日志间隔（秒）
_ERROR_DEBOUNCE_SECONDS = 120

# 瞬时故障重试：总尝试次数与逐次退避秒数（仅网络类异常/HTTP 429/5xx）
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = (2, 4)

# 限流场景的退避上限（秒）。Telegram 实测返回的 retry after 为 3~44 秒，
# 上界再留一倍余量；超过则按此上限等待，避免某次异常值把线程挂住过久。
_RETRY_AFTER_CAP_SECONDS = 60.0


def _parse_retry_after(error_text: str) -> float | None:
    """从 Telegram 的 429 响应文本里解析「建议等待秒数」。

    实测响应形如 `HTTP 429: Too Many Requests: retry after 32` ——
    该数值由服务端给出，**必须优先于本地固定退避**，否则本地等待（原为 2+4=6 秒）
    远小于服务端要求（实测 3~44 秒），3 次尝试会全部撞在限流上。

    解析失败或数值非正时返回 `None`，由调用方回退到固定退避。
    """
    import re

    match = re.search(r"retry after\s+(\d+(?:\.\d+)?)", error_text or "", re.I)
    if not match:
        return None
    try:
        seconds = float(match.group(1))
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return min(seconds, _RETRY_AFTER_CAP_SECONDS)


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
        """发送通知。瞬时故障按退避重试，配置类错误（401/404）不重试。

        **退避优先取服务端建议值**（限流时 Telegram 会在响应里给 `retry after N`）：
        本地固定退避（2+4=6 秒）**小于**服务端要求（实测 3~44 秒），只用本地值会让
        3 次尝试全部撞在限流上 → 通知丢失。故每次失败后用 `_parse_retry_after`
        读取 `last_error`，取到就用它（上限 60 秒），取不到才回退固定退避。
        """
        # 每次发送前重置错误详情，避免上次失败残留
        self.last_error = ""
        if not self._token or not self._chat_id:
            self.last_error = t("notification.channel.not_configured_telegram")
            return False
        # 使用电报渲染2文本
        # 标准号已由构建器渲染进正文（批次2 尾部重复行消除），发送层不再追加
        text = self._renderer.render(message)
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            ok, retryable = self._post_once(text)
            if ok:
                # 成功后清除错误去重状态
                self._last_error_key = ""
                self._last_error_time = 0.0
                return True
            if not retryable or attempt >= _MAX_ATTEMPTS:
                return False
            # 服务端建议等待优先；无建议则回退固定退避
            server_delay = _parse_retry_after(self.last_error)
            delay = server_delay if server_delay is not None else _RETRY_BACKOFF_SECONDS[attempt - 1]
            logger.warning(
                "Telegram 发送失败，%ss 后重试 (%d/%d): %s",
                delay,
                attempt,
                _MAX_ATTEMPTS,
                self.last_error,
            )
            time.sleep(delay)
        return False

    def _post_once(self, text: str) -> tuple[bool, bool]:
        """单次投递，返回 (是否成功, 是否可重试)；失败原因写入 last_error。

        可重试口径：网络类异常（含连接重置/握手超时）与 HTTP 429/5xx。
        401/404 属配置错误（token 无效/撤销），重试无意义。
        """
        payload = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
            }
        ).encode("utf-8")
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    if data.get("ok"):
                        return True, False
                    desc = data.get("description", "")
                    self.last_error = f"Telegram 返回失败: {desc}"
                    logger.warning("Telegram 通知失败: %s", desc)
                    return False, False
                # 真实网络库对非成功状态码会抛网络错误，此分支仅防御非标准实现
                self.last_error = f"Telegram HTTP {resp.status}"
                return False, False
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
            # 429/5xx→服务端临时故障，退避重试
            if e.code == 404:
                self._log_dedup(
                    "Telegram 404 — bot token 无效或已撤销，请检查配置中的 bot_token。"
                    " 在修复配置之前，Telegram 通知将静默跳过。"
                )
            elif e.code == 401:
                self._log_dedup("Telegram 401 Unauthorized — bot token 鉴权失败，请重新生成 token。")
            else:
                logger.warning("Telegram HTTP %s: %s", e.code, e)
            return False, e.code == 429 or e.code >= 500
        except OSError as e:
            # 网络类异常（连接重置/握手超时/域名解析失败，含网络库错误）属瞬时故障 → 退避重试
            self.last_error = f"Telegram 发送异常: {e}"
            logger.warning("Telegram 通知异常: %s", e)
            return False, True
        except Exception as e:
            # 非网络类异常（如解析/编程错误）重试无意义
            self.last_error = f"Telegram 发送异常: {e}"
            logger.warning("Telegram 通知异常: %s", e)
            return False, False

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

    # ── 渠道契约（第一版修订二：继承自渠道基类的通知渠道接口） ──

    @property
    def name(self) -> str:
        """渠道唯一标识。"""
        return "telegram"

    def test(self) -> bool:
        """发送一条测试消息验证渠道连通性。"""
        return self.send(
            NotificationMessage(
                title=t("notification.channel.test.title"),
                body=t("notification.channel.test.body"),
            )
        )

    def get_config_schema(self) -> dict[str, Any]:
        """渠道配置字段 schema（供前端动态渲染配置表单）——由 `channel_spec` 派生。"""
        from ..channel_spec import legacy_schema, spec_for

        return legacy_schema(spec_for(self.name), t)
