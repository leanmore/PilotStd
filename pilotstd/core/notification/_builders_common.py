"""事件构建器共享助手（T-41/5 从 `_builders_batch.py` 拆出，守 G-010）。

**依赖图（先行确认）**：本模块只依赖标准库与 `.blocks`/`.channel`；
`_builders_batch.py` 与 `_builders_batch_download.py` 都从本模块取助手 ⇒ **单向、无环**。
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from pilotstd.i18n import t


def _make_link(standard_number: str | None) -> str | None:
    """根据标准号生成跳转链接（与 _builders_system 同款，避免跨模块依赖）。

    链接用于站内跳转到标准详情页；标准号为空时返回 None（消息不含跳转）。
    """
    return f"/standards/{standard_number}" if standard_number else None


# 标准类型标签键（随 `_std_type_text` 一并迁入；主模块再导出以保持既有导入方兼容）
_STD_TYPE_LABEL_KEYS = {
    "NationalStd": "notification.common.std_type.national",
    "IndustryStd": "notification.common.std_type.industry",
    "LocalStd": "notification.common.std_type.local",
}


def _std_type_text(standard_type: str) -> str:
    """标准类型标签（未知类型返回空串，模板中省略该行）。"""
    key = _STD_TYPE_LABEL_KEYS.get(standard_type or "")
    return t(key) if key else ""


def _expected_download_date(publish_date: str) -> str:
    """预计自动下载日期 = 发布日期 + 冷却期天数。

    冷却期与收藏下载链同源（ARCHIVE_COOLDOWN_DAYS 环境变量，默认 28），
    避免双源漂移；日期无法解析时返回空串（模板回退为通用提示）。
    """
    if not publish_date:
        return ""
    try:
        d = date.fromisoformat(str(publish_date)[:10])
        cooldown = int(os.environ.get("ARCHIVE_COOLDOWN_DAYS", "28"))
        return (d + timedelta(days=cooldown)).isoformat()
    except (ValueError, TypeError):
        return ""
