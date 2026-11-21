"""通知里的"站内入口"链接解析与动作挂载（阶段 3 · Step 1）。

**要解决的问题（实测缺口）**：`view_detail` / `open_logs` 此前只有词表与三语文案，
**全库没有任何生产者** ⇒ 通知里永远没有"去站内看详情"的入口。

**取址口径（用户裁定）**：站内地址从**系统配置**读取（`notification.web_base_url`），
**未配置或不可用时必须优雅降级**——绝不能在聊天里生成 `http://localhost` 这类
"用户点不开"的链接。故本模块做两件事：

1. `resolve_web_base()`：校验并归一化 Base URL；
   · 必须 `http(s)://` 开头；
   · **拒绝回环/本机地址**（`localhost`/`127.0.0.1`/`0.0.0.0`/`::1`）——聊天接收方在**另一台机器**上，
     这类地址对他无意义（这是用户明确点名的"绝不能生成"的情形）；
   · 去掉尾部 `/`；非法一律返回空串（**降级**），并记 ASCII 开发者日志。
2. `attach_web_actions()`：把站内入口挂成**动作**（`ActionSpec`，`args={"url": …}`）；
   · 常态挂 `view_detail`（查看详情）；
   · **仅当该消息带失败明细**时**另挂** `open_logs`（打开通知日志）——语义不同：
     "有失败明细"时的下一步动作就是去日志页看细节；两者同址但**不会同时出现两个同义按钮**；
   · 地址不可用时**不挂动作**，改为追加一段**纯文本提示**（"请前往 Web 端「通知日志」查看"），
     即"按钮变提示"的降级（用户裁定允许的三种降级之一）。

**不做**：不猜 URL（不拼接未配置的域名、不用请求头里的 Host），不生成相对路径
（聊天客户端里相对路径无意义，等于坏链）。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol, TypeVar

logger = logging.getLogger(__name__)

# 配置键：站内页面的对外基址（公网域名或内网可达域名）
# 配置键：站内页面的对外基址
CONFIG_KEY = "notification.web_base_url"

# 站内「通知日志」页路径（前端路由；与 web/src 的页面一致）
LOGS_PATH = "/notification-logs"

_LOOPBACK = re.compile(
    r"^https?://(?:localhost|127(?:\.\d{1,3}){3}|0\.0\.0\.0|\[::1\])(?::\d+)?(?:/|$)",
    re.IGNORECASE,
)


def resolve_web_base(config: Any) -> str:
    """从配置取站内基址；不可用（未配置/非法/回环）返回空串。

    只认 `http://` 或 `https://` 开头的绝对地址；其余（含带空格、带路径查询的脏值）一律降级。
    """
    raw = ""
    try:
        raw = str(config.get(CONFIG_KEY, "") or "").strip()
    except Exception:  # 配置桩可能没有 get
        return ""
    if not raw:
        return ""
    if not raw.lower().startswith(("http://", "https://")):
        logger.debug("web base url ignored (not absolute): %r", raw)
        return ""
    if _LOOPBACK.match(raw):
        # 明确降级：聊天接收方在别的机器上，`localhost` 类地址点不开（用户明确要求不得生成）
        logger.debug("web base url ignored (loopback address): %r", raw)
        return ""
    return raw.rstrip("/")


def logs_url(base: str) -> str:
    """站内「通知日志」页完整地址（`base` 非空时调用）。"""
    return f"{base}{LOGS_PATH}" if base else ""


def attach_web_actions(message: Any, config: Any) -> bool:
    """按配置给消息挂"站内入口"动作；返回是否**成功挂上按钮**。

    · 成功：`view_detail`（+ 有失败明细时再挂 `open_logs`），两按钮都带 `args["url"]`；
    · 降级：地址不可用 ⇒ 不挂动作，改为**追加一段纯文本提示**（见下），返回 `False`。

    幂等：已有动作（如阶段 3 的业务动作）时**不覆盖**，只在其后**追加**站内入口。
    """
    from .blocks import TextBlock
    from .specs import ActionSpec

    base = resolve_web_base(config)
    url = logs_url(base)
    if not url:
        # 降级：一次消息只追加一段提示；同一消息发往多渠道时会被重复调用，不能重复追加。
        hint_text = _hint_text()
        blocks = list(getattr(message, "blocks", []) or [])
        if not any(getattr(b, "text", "") == hint_text for b in blocks):
            blocks.append(TextBlock(text=hint_text))
            message.blocks = blocks
        return False

    actions = list(getattr(message, "actions", []) or [])
    existing = {getattr(a, "action", "") for a in actions}
    if "view_detail" not in existing:
        actions.append(
            ActionSpec(action="view_detail", label_key="notification.action.view_detail", args={"url": url})
        )
    # 仅"有失败明细"时另挂 open_logs：那一步的下一步就是去日志页看细节
    if getattr(message, "failed_items", None) and "open_logs" not in existing:
        actions.append(
            ActionSpec(action="open_logs", label_key="notification.action.open_logs", args={"url": url})
        )
    message.actions = actions
    return True


def _hint_text() -> str:
    """降级提示文案（三语由 i18n 提供）。"""
    from pilotstd.i18n import t

    return t("notification.link.web_hint")

T = TypeVar("T", bound="_LinkMessage")


class _LinkMessage(Protocol):
    """只要求 `link` 字段的消息协议（避免 `_links` 反向依赖 `channel`）。"""

    link: "str | None"


def absolute_link(base: str, link: str) -> str:
    """把站内相对路径补成绝对地址；已是绝对地址原样返回；无基址则返回空串。

    渲染层只管展示：`message.link` 在构建期就应变成可点地址（否则聊天客户端里
    相对路径等于坏链），这里做纯函数转换，便于单测。
    """
    value = (link or "").strip()
    if not value:
        return ""
    if value.lower().startswith(("http://", "https://")):
        return value
    if not base:
        return ""
    return f"{base.rstrip('/')}/{value.lstrip('/')}"

def absolutize_message_link(message: T, config: Any) -> T:
    """构建期把 `message.link` 补成绝对地址；不可用则清空（宁可不给，也不给坏链）。"""
    link = str(getattr(message, "link", "") or "").strip()
    if not link:
        return message
    base = resolve_web_base(config)
    message.link = absolute_link(base, link) or None
    return message
