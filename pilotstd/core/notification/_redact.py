"""失败明细的**展示侧脱敏**（P3）：把 `error_message` 收敛为可安全透出的文本。

**口径（重要）**：**落库存真、展示脱敏**——`notification_log.failed_items` 仍保存原始报文
（排障需要原文，且它在同权限的 DB 内）；本模块只在**对外透出前**做拦截。

**为什么必须做**：`error_message` 的来源是业务异常与任务错误（实测：`_organize.py` 的异常文本、
`download/engine.py` 的任务错误），可能带**绝对路径**、**带查询串的下载 URL**（含临时签名/会话参数）、
**令牌样长串**、邮箱/手机号 ⇒ 直接透出给前端即"把排障信息当通知正文给用户看"。

**设计取舍**：
· **纯函数**（无 IO、无状态）⇒ 可单测、可在任意出口复用；
· **删减而非替换为提示语**：用户不需要看到"此处有敏感信息"这种元信息，掩码后保持可读即可；
· **长度上限**默认 120（与 B1 的 4 列口径一致）⇒ 超长截断加省略号。
"""

from __future__ import annotations

import re

# URL：保留 scheme://host/path，查询串与 fragment 一律折叠为 `?…`
_URL_WITH_QUERY = re.compile(r"(https?://[^\s?#]+)[?#][^\s]*", re.IGNORECASE)
# Windows 绝对路径：`C:\a\b\file.ext` ⇒ 只留末段
_WIN_PATH = re.compile(r"[A-Za-z]:\\[^\s]*")
# POSIX 绝对路径：`/a/b/file.ext` ⇒ 只留末段（避免误伤 URL：URL 已在上面折叠且 path 已被保留）
_POSIX_PATH = re.compile(r"(?<![\w:/])/(?:[^\s/]+/)+[^\s/]*")
# 令牌样长串：≥24 位的字母数字下划线连字符，或 ≥32 位十六进制
_LONG_TOKEN = re.compile(r"[A-Za-z0-9_\-]{24,}")
_HEX_TOKEN = re.compile(r"\b[0-9a-fA-F]{32,}\b")
# 邮箱：保留首字符与域名
_EMAIL = re.compile(r"([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*@([A-Za-z0-9.\-]+)")
# 中国大陆手机号
_PHONE = re.compile(r"\b1[3-9]\d{9}\b")

MASK = "***"


def redact_message(text: object, limit: int = 120) -> str:
    """把任意输入收敛为**可安全透出**的短文本（永不抛）。

    处理顺序（顺序即语义）：URL 查询串 → 绝对路径 → 长令牌 → 邮箱/手机号 → 截断。
    """
    if not isinstance(text, str):
        return ""
    value = text.strip()
    if not value:
        return ""

    value = _URL_WITH_QUERY.sub(r"\1?…", value)

    def _win(match: re.Match[str]) -> str:
        tail = match.group(0).replace("\\", "/").rsplit("/", 1)[-1]
        return f"…/{tail}" if tail else "…"

    def _posix(match: re.Match[str]) -> str:
        tail = match.group(0).rstrip("/").rsplit("/", 1)[-1]
        return f"…/{tail}" if tail else "…"

    value = _WIN_PATH.sub(_win, value)
    value = _POSIX_PATH.sub(_posix, value)
    value = _HEX_TOKEN.sub(MASK, value)
    value = _LONG_TOKEN.sub(MASK, value)
    value = _EMAIL.sub(r"\1***@\2", value)
    value = _PHONE.sub("1**********", value)

    if limit > 0 and len(value) > limit:
        value = value[:limit].rstrip() + "…"
    return value
