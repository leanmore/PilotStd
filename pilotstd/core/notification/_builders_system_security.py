"""安全族事件构建器（T-41/5 (2/2) 从 `_builders_system.py` 拆出，守 G-010）。

**职责**：`notification_credential_changed` / `security_password_changed` / `security_token_refreshed` /
`security_login_failed` 四条安全事件的构建器。
**依赖纪律**：只用 `pilotstd.i18n` 与 `.blocks`/`.channel`；**不依赖** `_builders_batch`（既无顶层 import
也无函数内惰性 import——这四条构建器不需要失败明细块），避免任何加载顺序风险。
"""

from __future__ import annotations

from pilotstd.i18n import t

from .blocks import (
    KeyValueBlock,
    NotificationBlock,
    TextBlock,
)
from .channel import NotificationMessage


# 通知凭证变更：改动面与影响范围并重（安全审计要求），并给出回滚提示。
def _build_notification_credential_changed_message(data: dict) -> NotificationMessage:
    """通知渠道凭证变更告警。

    载荷：services（被改动渠道）、changed_keys（被改动字段名）、rules_changed、
    from_ip。**载荷与日志均不含凭证值**——变更告警的价值在于"知道被改"，
    回显凭证会让告警本身成为泄露面。
    """
    services = [str(s) for s in (data.get("services") or [])]
    changed_keys = [str(k) for k in (data.get("changed_keys") or [])]
    rules_changed = bool(data.get("rules_changed"))
    from_ip = str(data.get("from_ip") or "")

    blocks: list[NotificationBlock] = []
    if services:
        blocks.append(
            KeyValueBlock(
                key=t("notification.system.notification_credential_changed.body.services"),
                value=", ".join(services),
            )
        )
    if changed_keys:
        blocks.append(
            KeyValueBlock(
                key=t("notification.system.notification_credential_changed.body.keys"),
                value=", ".join(changed_keys),
            )
        )
    if not services and rules_changed:
        blocks.append(TextBlock(text=t("notification.system.notification_credential_changed.body.rules")))
    if from_ip:
        blocks.append(
            KeyValueBlock(
                key=t("notification.system.notification_credential_changed.body.from_ip"),
                value=from_ip,
            )
        )
    blocks.append(TextBlock(text=t("notification.system.notification_credential_changed.body.hint")))

    return NotificationMessage(
        title=t("notification.system.notification_credential_changed.title"),
        blocks=blocks,
        level="warning",
        event_type="notification_credential_changed",
        icon="pi pi-shield",
    )


# 密码变更：提示「若非本人操作立即改回」，属安全事件（写审计）。
def _build_security_password_changed_message(data: dict) -> NotificationMessage:
    """账号密码变更告警。

    载荷：user_id、from_ip、sessions_revoked（**撤销会话数**，L-03 后为真实值；原为恒 False）。

    仅当撤销数为 0 时才附加"既有会话未失效"提示——正常路径下 L-03 会撤销全部会话，
    故该提示不应出现；保留分支是为了让"撤销数为 0"这一异常情形在用户可见文案中显式暴露。
    """
    user_id = str(data.get("user_id") or "")
    from_ip = str(data.get("from_ip") or "")
    sessions_revoked = bool(data.get("sessions_revoked"))

    blocks: list[NotificationBlock] = []
    if user_id:
        blocks.append(
            KeyValueBlock(key=t("notification.system.security_password_changed.body.account"), value=user_id)
        )
    if from_ip:
        blocks.append(
            KeyValueBlock(key=t("notification.system.security_password_changed.body.from_ip"), value=from_ip)
        )
    if not sessions_revoked:
        # 撤销数为 0（异常情形）：L-03 本应撤销全部会话，故此处必须在**用户可见文案**中
        # 显式提示，否则用户会误以为改密已踢掉其它登录。
        blocks.append(TextBlock(text=t("notification.system.security_password_changed.body.sessions_kept")))
    blocks.append(TextBlock(text=t("notification.system.security_password_changed.body.hint")))

    return NotificationMessage(
        title=t("notification.system.security_password_changed.title"),
        blocks=blocks,
        level="warning",
        event_type="security_password_changed",
        icon="pi pi-key",
    )


# 令牌刷新：告知新有效期与来源 IP，便于用户核对是否本人操作。
def _build_security_token_refreshed_message(data: dict) -> NotificationMessage:
    """静态 API 令牌轮换告警。载荷：rotated_at、from_ip、db_synced。绝不包含令牌值。"""
    rotated_at = str(data.get("rotated_at") or "")
    from_ip = str(data.get("from_ip") or "")
    db_synced = bool(data.get("db_synced", True))

    blocks: list[NotificationBlock] = []
    if rotated_at:
        blocks.append(
            KeyValueBlock(key=t("notification.system.security_token_refreshed.body.time"), value=rotated_at)
        )
    if from_ip:
        blocks.append(
            KeyValueBlock(key=t("notification.system.security_token_refreshed.body.from_ip"), value=from_ip)
        )
    if not db_synced:
        blocks.append(TextBlock(text=t("notification.system.security_token_refreshed.body.db_unsynced")))
    blocks.append(TextBlock(text=t("notification.system.security_token_refreshed.body.hint")))

    return NotificationMessage(
        title=t("notification.system.security_token_refreshed.title"),
        blocks=blocks,
        level="warning",
        event_type="security_token_refreshed",
        icon="pi pi-refresh",
    )


# 登录失败：累计次数与来源 IP 是判断暴力破解的关键，必须逐条可见。
def _build_security_login_failed_message(data: dict) -> NotificationMessage:
    """登录失败告警（第 8 批，P0 安全事件）。

    载荷：from_ip、failures、window_seconds、username。
    **不回显密码**；用户名照常展示——登录失败响应本身不区分"用户不存在"与
    "密码错误"（防用户名枚举），但一旦达到告警阈值，账号所有者需要知道
    "有人在试哪个账号"，否则无法判断是否针对自己。
    """
    from_ip = str(data.get("from_ip") or "")
    failures = data.get("failures", 0)
    window_seconds = data.get("window_seconds", 0)
    username = str(data.get("username") or "")

    blocks: list[NotificationBlock] = []
    try:
        window_minutes = max(1, int(window_seconds) // 60)
    except (TypeError, ValueError):
        window_minutes = 0
    blocks.append(
        TextBlock(
            text=t("notification.system.security_login_failed.body.count").format(
                n=failures, minutes=window_minutes
            )
        )
    )
    if username:
        blocks.append(
            KeyValueBlock(
                key=t("notification.system.security_login_failed.body.account"), value=username
            )
        )
    if from_ip:
        blocks.append(
            KeyValueBlock(
                key=t("notification.system.security_login_failed.body.from_ip"), value=from_ip
            )
        )
    blocks.append(TextBlock(text=t("notification.system.security_login_failed.body.hint")))

    return NotificationMessage(
        title=t("notification.system.security_login_failed.title"),
        blocks=blocks,
        level="warning",
        event_type="security_login_failed",
        icon="pi pi-lock",
    )
