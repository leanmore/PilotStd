# 模块：项目/界面/错误格式化
"""把底层 OSError/PermissionError 转成桌面端可读中文提示，统一 UI 错误出口。"""

from __future__ import annotations

from ..i18n import _


def format_ui_error(exc: BaseException) -> str:
    """文件占用/权限/磁盘满等常见 Windows 错误 → 中文提示（含文件名）。"""
    text = str(exc)
    name = text.split("'")[1] if "'" in text else ""
    if getattr(exc, "errno", None) == 28 or "WinError 112" in text:
        return _("ui_err_disk_full").format(name=name or text)
    if (
        "WinError 32" in text
        or "WinError 33" in text
        or "being used by another process" in text
        or "cannot access the file" in text.lower()
    ):
        return _("ui_err_file_in_use").format(name=name or text)
    if isinstance(exc, PermissionError) or "WinError 5" in text:
        return _("ui_err_permission").format(name=name or text)
    return text
