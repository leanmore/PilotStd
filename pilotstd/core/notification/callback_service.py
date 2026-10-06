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
import logging
from dataclasses import dataclass
from typing import Any

from pilotstd.i18n import t

from .callback import (
    STATUS_FORBIDDEN,
    STATUS_GONE,
    STATUS_OK,
    STATUS_UNAUTHORIZED,
    ActionVerdictLike,
    authorize_action,
    parse_envelope,
    verify_callback,
)
from .callback_store import LogBackedReplayGuard

logger = logging.getLogger(__name__)


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


def _execute_action(db: Any, action: str, log_id: int, channel: str, creds: dict[str, Any]) -> bool:
    """执行动作：`ignore` / `snooze` 更新 ack_status；`retry` **真正重投**该条通知。

    `creds` 是**该用户该渠道的完整（已解密）凭证字典**——重投需要它按
    `channel_spec.spec_for(channel).ctor` 重建渠道实例（与 `manager._init_channels` 同一驱动），
    只传 `secret` 是不够的（构造还可能要 `bot_token`/`chat_id`/`webhook_url` 等）。
    """
    # 重投走渠道再发（真发结果写同一行）；其余两个动作只是状态标记
    if action == "retry":
        return _retry(db, log_id, channel, creds)
    status = "ignored" if action == "ignore" else "snoozed"
    db.execute("UPDATE notification_log SET ack_status = ? WHERE id = ?", (status, log_id))
    return True


def _retry(db: Any, log_id: int, channel: str, creds: dict[str, Any]) -> bool:
    """**真正重投**：按日志行里的标题/正文重建消息，经渠道再发一次，结果写回同一行。

    与 `manager._init_channels` 共用同一构造口径（`spec.ctor` 按序传参 + `ctor_required` 非空校验），
    避免"两处各写一份构造规则"的漂移。

    **结果口径**：
    · 先写 `ack_status='retry_requested'`（如实记录"用户点了重投"）；
    · 再按**真发结果**回写 `status`（`success`/`failed`）与 `error_msg`（渠道 `last_error`）；
    · 构造不出来（凭证缺失/渠道未启用）或行不存在 ⇒ 返回 `False`（调用方据此回 403），
      **不**把"没发出去"记成成功。
    """
    from .channel import NotificationMessage
    from .channel_spec import channel_class, spec_for

    rows = db.fetchall(
        "SELECT title, body, event_type FROM notification_log WHERE id = ? LIMIT 1", (log_id,)
    )
    if not rows:
        return False
    row = rows[0]

    # ① 如实记录"重投已被请求"（无论后续成败）
    db.execute(
        "UPDATE notification_log SET ack_status = ? WHERE id = ?", ("retry_requested", log_id)
    )

    # ② 构造渠道：与 `_init_channels` 同一驱动（按 `ctor` 取参、按 `ctor_required` 校验）
    spec = spec_for(channel)
    ch_cfg = dict(creds or {})
    enabled = ch_cfg.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() not in ("false", "0", "")
    args = tuple(str(ch_cfg.get(f) or "").strip() for f in spec.ctor)
    guards = tuple(str(ch_cfg.get(f) or "").strip() for f in spec.ctor_required)
    if not enabled or not all(guards):
        logger.warning(
            "notification retry skipped: channel %s not configured or disabled (log_id=%s)",
            channel,
            log_id,
        )
        return False
    try:
        ch = channel_class(spec)(*args)
    except Exception as e:
        logger.warning("notification retry: channel %s build failed: %s", channel, e)
        return False

    # ③ 真发（重建最小消息：标题/正文/事件类型取自该日志行）
    msg = NotificationMessage(title=str(row.get("title") or ""))
    msg.body = str(row.get("body") or "")
    msg.event_type = str(row.get("event_type") or "")
    try:
        ok = bool(ch.send(msg))
        err_msg = "" if ok else (getattr(ch, "last_error", "") or "retry failed")
    except Exception as e:  # 渠道异常不得让回调端点 500
        ok, err_msg = False, str(e)
        logger.warning("notification retry: channel %s send raised: %s", channel, e)

    # ④ 真发结果写回同一行（只动 status/error_msg，不臆造 delivery_status 枚举值）
    db.execute(
        "UPDATE notification_log SET status = ?, error_msg = ? WHERE id = ?",
        ("success" if ok else "failed", err_msg, log_id),
    )
    return ok


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
        # 区分两类（阶段 3 · P5b 用户裁定）：
        #   ① **畸形/缺失 token** ⇒ 仍与验签失败同码（401）：不给攻击者一个可枚举的探针面；
        #   ② **格式合法但记录已不存在**（日志按保留策略清理后用户点了旧按钮）⇒ **410 优雅降级**，
        #      提示"操作已失效"，而不是 500/无响应，也不是语焉不详的"签名错误"。
        if _is_wellformed_token(envelope.callback_data):
            return _fail(STATUS_GONE, "notification.callback.action_expired")
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

    if not _execute_action(db, envelope.action, log_id, channel, creds):
        return _fail(STATUS_FORBIDDEN, "notification.callback.forbidden")
    return CallbackOutcome(status=STATUS_OK, payload={"ok": True})


def _is_wellformed_token(token: str) -> bool:
    """token 是否形如 `"<log_id>:<user_id>"`（两段纯数字）。

    仅用于**区分降级提示的措辞**（410 与 401），**不构成任何信任**：身份仍由验签 + DB 角色决定。
    畸形/缺失一律按 401，避免把"哪些 id 存在"变成可枚举信息。
    """
    head, sep, tail = token.partition(":")
    return bool(sep) and head.isdigit() and tail.isdigit()


def describe_outcome(outcome: CallbackOutcome) -> str:
    """日志用摘要（不含载荷原文）。"""
    if outcome.reason_key:
        return f"status={outcome.status} reason={t(outcome.reason_key)}"
    return f"status={outcome.status} ok"
