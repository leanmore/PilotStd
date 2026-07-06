# pilotstd/core/notification/desktop_formatter.py
"""桌面端 Windows Toast 格式化——剥离 Emoji、截断长度、纯文本排版。

新版聚合器 format_summary 面向 Telegram/飞书等 Web 渠道，使用了 ✅❌⏱️ 等 Emoji。
Windows 原生 QSystemTrayIcon.showMessage() 对这些字符渲染不稳定，
旧版系统可能显示为乱码。本模块提供去 Emoji + 长度保护的纯净格式化。
"""

import re

# Windows Toast 气泡空间有限
MAX_TITLE_LENGTH = 40
MAX_BODY_LENGTH = 120

EMOJI_MAP = {
    "✅": "[成功]",
    "❌": "[失败]",
    "⏱️": "[耗时]",
    "⏱": "[耗时]",
    "⚠️": "[警告]",
    "ℹ️": "[提示]",
    "📦": "",
    "📋": "",
}


def format_for_desktop(title: str, body: str) -> tuple[str, str]:
    """将聚合后的消息转为 Windows Toast 安全格式。

    1. Emoji → 纯文本标签
    2. 多行合并为单行（Toast 气泡不支持多行）
    3. 超长截断加省略号
    """
    safe_title = title
    safe_body = body
    for emoji, text in EMOJI_MAP.items():
        safe_title = safe_title.replace(emoji, text)
        safe_body = safe_body.replace(emoji, text)

    # 多余空白压缩，换行转空格
    safe_title = re.sub(r"\s+", " ", safe_title).strip()
    safe_body = re.sub(r"\s+", " ", safe_body).strip()

    # 长度保护
    if len(safe_title) > MAX_TITLE_LENGTH:
        safe_title = safe_title[: MAX_TITLE_LENGTH - 3] + "..."
    if len(safe_body) > MAX_BODY_LENGTH:
        safe_body = safe_body[: MAX_BODY_LENGTH - 3] + "..."

    return safe_title, safe_body
