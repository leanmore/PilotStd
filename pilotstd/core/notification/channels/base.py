# 模块：项目/核心//渠道/脚本
"""渠道抽象基类（v1.1 R2，MoviePilot 风格）——所有通知渠道的统一契约。

设计要点：
- send(): 发送通知（失败填充 last_error 供管理层写入发送日志）
- test(): 发送测试消息验证连通性（供配置页"测试连接"使用）
- name: 渠道唯一标识（telegram/wechat/dingtalk/feishu，与 _CHANNEL_CLASSES 键一致）
- get_config_schema(): 渠道配置字段 schema（供前端动态渲染配置表单）
- 配置以 DB（user_credentials，经 CredentialHelper）为唯一真实数据源（SSOT）；
  config.json 仅作一次性显式迁移源（migrate_from_config_if_empty），运行时不再读取

与 channel.py 中旧 NotificationChannel 的关系：本类为规范基类（v1.1 R2），
channel.py 旧基类保留仅为公共导出兼容（__init__.py），不再被任何渠道继承。
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from pilotstd.i18n import t

from ..channel import NotificationMessage

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查
    from ..interaction import ChannelCapabilities, MessageHandle

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════ 分隔
# 瞬时故障重试与限流退避（2026-10-17 从 telegram 单点提升为**渠道基座**）
#
# 背景（实测）：重试/退避此前只长在 telegram 一家（该文件 27 处相关命中），
# dingtalk / feishu / wechat 各仅 0~1 处、`base.py` 为 0 ⇒ 同样一次 429 或网络抖动，
# 只有 telegram 会退避重试，其余三家**当场丢通知**。"渠道能不能用是用户的选择，
# 但基础能力必须各家一致"——故把节奏、限流解析与错误去重提到基类，各渠道复用。
# ════════════════════════════════════════════════════════════════ 分隔

# 总尝试次数与逐次固定退避秒数（仅在服务端未给"建议等待"时使用）
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (2, 4)

# 服务端建议等待的**上限**（秒）：避免某次异常值把线程挂住过久（Telegram 实测 3~44 秒）
RETRY_AFTER_CAP_SECONDS = 60.0

# 永久性错误去重：同一错误信息的最小日志间隔（秒）
ERROR_DEBOUNCE_SECONDS = 120

# 限流关键词兜底：各家的限流**错误码未逐家取证**（钉钉官方文档为 JS 渲染、取不到正文），
# 故除 HTTP 429/5xx 外，再按响应文本里的通用措辞兜一层；取证到具体码后应改为按码判定。
_RATE_LIMIT_HINTS = (
    "retry after",
    "too many request",
    "rate limit",
    "ratelimit",
    "too fast",
    # i18n-allow: 匹配站点响应里的中文限流措辞，翻译即失效
    "限流", "频繁", "超过限制",
)


def parse_retry_after(error_text: str) -> float | None:
    """从响应文本里解析服务端「建议等待秒数」（形如 `retry after 32`）。

    服务端给出的数值**必须优先于本地固定退避**：实测 Telegram 的该值为 3~44 秒，
    而本地固定退避只有 2+4=6 秒 ⇒ 只用本地值会让 3 次尝试全部撞在限流上。

    解析失败或数值非正时返回 `None`，由调用方回退固定退避；结果按
    `RETRY_AFTER_CAP_SECONDS` 截顶。
    """
    import re

    match = re.search(r"retry after\s+(\d+(?:\.\d+)?)", str(error_text or ""), re.I)
    if not match:
        return None
    try:
        seconds = float(match.group(1))
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return min(seconds, RETRY_AFTER_CAP_SECONDS)


def is_retryable_http_status(status: int) -> bool:
    """HTTP 状态是否属"可重试"的瞬时故障：429（限流）与 5xx（服务端故障）。"""
    return status == 429 or status >= 500


def looks_rate_limited(text: str) -> bool:
    """响应文本是否像限流（各家错误码未取证时的兜底判据）。"""
    lowered = (text or "").lower()
    return any(hint in lowered for hint in _RATE_LIMIT_HINTS)


# A-42（T-42）：已取证的渠道限流错误码。查不到的渠道保持空集 + 关键词兜底。
CHANNEL_RATE_LIMIT_CODES: dict[str, frozenset[int]] = {
    "wechat": frozenset({45009}),  # api freq out of limit
    "feishu": frozenset({99991400}),  # request trigger frequency limit
    "dingtalk": frozenset(),  # 官方文档为 JS 渲染，暂未取证
    "telegram": frozenset(),  # 仅 HTTP 429，无业务码
}


def is_rate_limited(channel: str, code: object, text: str) -> bool:
    """限流判定：**码优先**，未取证/未命中码时回退关键词。"""
    try:
        numeric = int(str(code))
    except (TypeError, ValueError):
        numeric = None
    if numeric is not None and numeric in CHANNEL_RATE_LIMIT_CODES.get(channel, frozenset()):
        return True
    return looks_rate_limited(text)


class NotificationChannel(ABC):
    """通知渠道抽象基类。"""

    def __init__(self) -> None:
        # 错误详情透传：发送失败时由子类填充具体原因供管理层读取
        self.last_error: str = ""

    # ── 统一重试驱动（各家 send() 复用，避免"只有 telegram 会重试"）──

    def _log_dedup(self, msg: str) -> None:
        """去重日志：相同消息在 `ERROR_DEBOUNCE_SECONDS` 内只记一次。

        用 `getattr` 读状态：历史渠道的 `__init__` 未调用 `super().__init__()`，
        不能假设这两个属性一定已初始化。
        """
        now = time.monotonic()
        if (
            msg == getattr(self, "_last_error_key", "")
            and (now - getattr(self, "_last_error_time", 0.0)) < ERROR_DEBOUNCE_SECONDS
        ):
            return
        self._last_error_key = msg
        self._last_error_time = now
        logger.error(msg)

    def _with_retry(self, attempt_fn: Callable[[int], "tuple[bool, bool]"]) -> bool:
        """按统一节奏投递一次：失败可重试则退避后重试，最多 `MAX_ATTEMPTS` 次。

        `attempt_fn(attempt)` 返回 `(ok, retryable)`，并把失败原因写进 `self.last_error`；
        退避优先取服务端建议值（`parse_retry_after(self.last_error)`，取不到才用固定退避）。
        任一次成功即清空错误去重状态（与 telegram 原实现同口径）。
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            ok, retryable = attempt_fn(attempt)
            if ok:
                self._last_error_key = ""
                self._last_error_time = 0.0
                return True
            if not retryable or attempt >= MAX_ATTEMPTS:
                return False
            server_delay = parse_retry_after(self.last_error)
            fallback = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
            delay = server_delay if server_delay is not None else fallback
            logger.warning(
                # i18n-allow: 开发者日志（重试节奏与失败原因，不进 i18n）
                "%s 发送失败，%ss 后重试 (%d/%d): %s",
                self.name,
                delay,
                attempt,
                MAX_ATTEMPTS,
                self.last_error,
            )
            time.sleep(delay)
        return False

    @abstractmethod
    def send(self, message: NotificationMessage) -> bool:
        """发送通知，成功返回真；失败返回假并应填充 last_error 属性。"""

    @abstractmethod
    def test(self) -> bool:
        """发送一条测试消息验证渠道连通性，返回是否发送成功。"""

    @property
    def capabilities(self) -> "ChannelCapabilities":
        """渠道交互能力（默认：不支持回调、不支持编辑）。

        渠道按自身形态覆盖；**不能编辑不等于故障**——四家锚点本就不同（设计 §四 结论 3），
        缺失是能力事实，`ChannelCapabilities.note_key` 负责解释原因。
        """
        from ..interaction import ChannelCapabilities

        return ChannelCapabilities()

    def edit_message(self, handle: "MessageHandle", message: NotificationMessage) -> bool:
        """按改写句柄更新已发出的消息（默认不支持）。

        默认实现返回 False 并写 `last_error`（与 `send()` 同口径：失败必须可见），
        由具备能力的渠道覆盖。
        """
        del handle, message
        self.last_error = t("notification.channel.edit_unsupported")
        return False

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道唯一标识（与 _CHANNEL_CLASSES 键一致）。"""

    @abstractmethod
    def get_config_schema(self) -> dict[str, Any]:
        """渠道配置字段 schema，供前端动态渲染配置表单。"""

    @staticmethod
    def validate_config(config: dict) -> bool:
        """验证渠道配置是否完整。子类可覆盖。"""
        return True
