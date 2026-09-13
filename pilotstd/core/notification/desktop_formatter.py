# 模块：项目/核心//_脚本
"""桌面端 Windows Toast 格式化——剥离 Emoji、截断长度、纯文本排版。

新版聚合器 format_summary 面向 Telegram/飞书等 Web 渠道，使用了 ✅❌⏱️ 等 Emoji。
Windows 原生 QSystemTrayIcon.showMessage() 对这些字符渲染不稳定，
旧版系统可能显示为乱码。本模块提供去 Emoji + 长度保护的纯净格式化。
"""

from __future__ import annotations

import re

from pilotstd.i18n import t

from .channel import NotificationMessage
from .renderer import DesktopRenderer

# 气泡空间有限
MAX_TITLE_LENGTH = 40
MAX_BODY_LENGTH = 120

# 桌面气泡不支持的 Emoji → 纯文本标签的 i18n 键（空串表示直接删除）
# 只存键、渲染时取 t()：模块级直接求值会把语言固化在 import 时刻。
_EMOJI_LABEL_KEYS = {
    "✅": "notification.desktop.level.success",
    "❌": "notification.desktop.level.failure",
    "⏱️": "notification.desktop.level.elapsed",
    "⏱": "notification.desktop.level.elapsed",
    "⚠️": "notification.desktop.level.warning",
    "ℹ️": "notification.desktop.level.info",
    "📦": "",
    "📋": "",
}

# 模块级渲染器实例——桌面端只有一种渲染风格，不需要每次
_desktop_renderer = DesktopRenderer()


def render_for_desktop(message: NotificationMessage) -> tuple[str, str]:
    """使用 DesktopRenderer 渲染消息，再经 Emoji 替换 + 截断保护。

    返回 (safe_title, safe_body) 可直接传给 QSystemTrayIcon.showMessage()。
    """
    body = _desktop_renderer.render(message)
    return format_for_desktop(message.title, body)


def format_for_desktop(title: str, body: str) -> tuple[str, str]:
    """将聚合后的消息转为 Windows Toast 安全格式。

    1. Emoji → 纯文本标签
    2. 多行合并为单行（Toast 气泡不支持多行）
    3. 超长截断加省略号
    """
    safe_title = title
    safe_body = body
    for emoji, key in _EMOJI_LABEL_KEYS.items():
        label = t(key) if key else ""
        safe_title = safe_title.replace(emoji, label)
        safe_body = safe_body.replace(emoji, label)

    # 多余空白压缩，换行转空格
    safe_title = re.sub(r"\s+", " ", safe_title).strip()
    safe_body = re.sub(r"\s+", " ", safe_body).strip()

    # 长度保护
    if len(safe_title) > MAX_TITLE_LENGTH:
        safe_title = safe_title[: MAX_TITLE_LENGTH - 3] + "..."
    if len(safe_body) > MAX_BODY_LENGTH:
        safe_body = safe_body[: MAX_BODY_LENGTH - 3] + "..."

    return safe_title, safe_body
