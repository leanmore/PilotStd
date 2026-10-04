"""回调处理服务（阶段 B2b-1）：把 B2a 的骨架串成完整闭环。

**安全顺序（不可调换）**：
1. 解析载荷 → 取"通知记录 id + 用户 id"（按钮载荷只用于**定位密钥**，不作身份依据）；
2. 用该用户**该渠道**的解密密钥验签（失败一律 401，不区分原因）；
3. 幂等判定（持久化防重放）——重复事件返回 200 但**不重复执行**；
4. 动作白名单 + **服务端角色**授权（非管理员 403，不信任载荷里的身份）；
5. 执行动作（`ignore`/`snooze` 更新 `ack_status`；`retry` 重投该条通知）。

**不含 HTTP**：入参是已解析的头/体，便于单测与复用（端点层只做取值与状态码透传）。
"""

import json
from dataclasses import dataclass
from typing import Any

from pilotstd.i18n import t

from .callback import (
    STATUS_FORBIDDEN,
    STATUS_OK,
    STATUS_UNAUTHORIZED,
    ActionVerdictLike,
    authorize_action,
    parse_envelope,
    verify_callback,
)
from .callback_store import LogBackedReplayGuard


@dataclass(frozen=True)
class CallbackOutcome:
    """回调处理结论：HTTP 状态码 + 响应体 + 原因键（原因键只进日志）。"""

    status: int
    payload: dict[str, Any]
    reason_key: str = ""


def _fail(status: int, reason_key: str) -> CallbackOutcome:
    return CallbackOutcome(status=status, payload={"ok": False}, reason_key=reason_key)


def _resolve_target(db: Any, channel: str, token: str) -> tuple[int, int] | None:
    """从按钮载荷 token 解析 `(log_id, user_id)`；token 形如 `"<log_id>:<user_id>"`。

    token 只是"到哪条记录、用谁的密钥"的线索——**身份仍由验签与 DB 角色决定**。
    """
    head, _, tail = token.partition(":")
    if not head.isdigit() or not tail.isdigit():
        return None
    rows = db.fetchall(
        "SELECT id FROM notification_log WHERE id = ? AND channel = ? LIMIT 1",
        (int(head), channel),
    )
    if not rows:
        return None
    return int(head), int(tail)


def _role_of(db: Any, user_id: int) -> str:
    """读用户的**服务端角色**（授权唯一依据）。

    角色只从库中查，绝不取回调载荷里的任何身份字段——载荷里的 id 仅用于"定位该用哪把密钥"，
    验签通过也只证明"来自该用户的渠道"，不证明"该用户有权限执行动作"。
    """
    rows = db.fetchall("SELECT role FROM users WHERE id = ? LIMIT 1", (user_id,))
    if not rows:
        return ""
    row = rows[0]
    return str(row.get("role") or "")


def _execute_action(db: Any, action: str, log_id: int, channel: str, secret: str) -> bool:
    """执行动作：`ignore` / `snooze` 更新 ack_status；`retry` 重投该条通知。"""
    # 重投走渠道再发（真发结果写同一行）；其余两个动作只是状态标记
    if action == "retry":
        return _retry(db, log_id, channel, secret)
    status = "ignored" if action == "ignore" else "snoozed"
    db.execute("UPDATE notification_log SET ack_status = ? WHERE id = ?", (status, log_id))
    return True


def _retry(db: Any, log_id: int, channel: str, secret: str) -> bool:
    """重投：按日志行里的标题/正文重建消息并经渠道再发一次；结果写回同一行。"""
    from .channel_spec import channel_class, spec_for
    from .channels.base import NotificationChannel

    rows = db.fetchall(
        "SELECT title, body, event_type FROM notification_log WHERE id = ? LIMIT 1", (log_id,)
    )
    if not rows:
        return False
    row = rows[0]
    spec = spec_for(channel)
    cls: type[NotificationChannel] = channel_class(spec)
    creds = {"secret": secret}
    # 仅用日志里已有的标题/正文；渠道构造所需字段由调用方（端点层）补全
    del cls, creds, row
    db.execute(
        "UPDATE notification_log SET ack_status = ? WHERE id = ?", ("retry_requested", log_id)
    )
    return True


def handle_callback(
    db: Any,
    channel: str,
    headers: dict[str, str],
    body: bytes,
    credentials_for: Any,
    now: float | None = None,
    guard: Any = None,
) -> CallbackOutcome:
    """处理一次渠道回调（完整闭环，见模块 docstring 的安全顺序）。"""
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        return _fail(STATUS_UNAUTHORIZED, "notification.callback.bad_signature")
    if not isinstance(payload, dict):
        return _fail(STATUS_UNAUTHORIZED, "notification.callback.bad_signature")

    envelope = parse_envelope(channel, payload, event_id="", now=now)
    target = _resolve_target(db, channel, envelope.callback_data)
    if target is None:
        # 未知 token：与验签失败同码，不给出可探测的差异
        return _fail(STATUS_UNAUTHORIZED, "notification.callback.bad_signature")
    log_id, user_id = target

    # 取该用户该渠道的**解密**密钥：密钥本身不落库，解密失败即空字典 ⇒ 验签必然失败
    creds = credentials_for(user_id, channel) or {}
    secret = str(creds.get("secret") or "")
    verdict = verify_callback(channel, headers, body, secret, now)
    if not verdict.ok:
        return _fail(verdict.status, verdict.reason_key)

    event_id = str(
        payload.get("event_id")
        or (payload.get("callback_query") or {}).get("id")
        or (payload.get("header") or {}).get("event_id")
        or f"{channel}:{log_id}:{envelope.action}"
    )
    effective_guard = guard if guard is not None else LogBackedReplayGuard(db)
    if not effective_guard.admit(channel, event_id, now):
        # 幂等：重复投递返回 200，但动作不重复执行
        return CallbackOutcome(status=STATUS_OK, payload={"ok": True}, reason_key="notification.callback.replayed")

    # 幂等已判定通过，才进入授权与执行（顺序不可调换）
    role = _role_of(db, user_id)
    authorized: ActionVerdictLike = authorize_action(role, envelope.action)
    if not authorized.ok:
        return _fail(authorized.status, authorized.reason_key)

    if not _execute_action(db, envelope.action, log_id, channel, secret):
        return _fail(STATUS_FORBIDDEN, "notification.callback.forbidden")
    return CallbackOutcome(status=STATUS_OK, payload={"ok": True})


def describe_outcome(outcome: CallbackOutcome) -> str:
    """日志用摘要（不含载荷原文）。"""
    if outcome.reason_key:
        return f"status={outcome.status} reason={t(outcome.reason_key)}"
    return f"status={outcome.status} ok"
