"""通知配置分层：系统级 / 用户级归属（A-28，决策 C）。

本模块只做**归属判定**，不改变读写路径；迁移脚本与后续读路径共用。
"""

from __future__ import annotations

SYSTEM_KEYS: frozenset[str] = frozenset(
    {
        "notification.enabled",
        "notification.web_base_url",
        "notification.logs.task_context_whitelist",
    }
)

# 前缀归系统级：回调密钥/URL、渠道级凭证
SYSTEM_PREFIXES: tuple[str, ...] = ("notification.callback.",)

# 前缀归用户级：事件订阅规则（数据库策略已是用户级）、渠道凭证（按用户）
USER_PREFIXES: tuple[str, ...] = ("notification.rules.", "notification.channels.")

# 用户级精确键：静音时段（当前存 config，迁移到用户偏好）
USER_KEYS: frozenset[str] = frozenset(
    {
        "notification.quiet_hours_enabled",
        "notification.quiet_hours_start",
        "notification.quiet_hours_end",
    }
)


def scope_of(key: str) -> str:
    """返回 `system` 或 `user`；未知键按用户级（与迁移白名单同口径）。"""
    if key in SYSTEM_KEYS or key.startswith(SYSTEM_PREFIXES):
        return "system"
    if key in USER_KEYS or key.startswith(USER_PREFIXES):
        return "user"
    return "user"
