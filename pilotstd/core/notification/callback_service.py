"""回调处理服务（阶段 B2b-1）：把 B2a 的骨架串成完整闭环。

**安全顺序（不可调换）**：
1. 解析载荷 → 取"通知记录 id + 用户 id"（按钮载荷只用于**定位密钥**，不作身份依据）；
2. 用该用户**该渠道**的解密密钥验签（失败一律 401，不区分原因）；
3. 幂等判定（持久化防重放）——重复事件返回 200 但**不重复执行**；
4. 动作白名单 + **服务端角色**授权（非管理员 403，不信任载荷里的身份）；
5. 执行动作（`ignore`/`snooze` 更新 `ack_status`；`retry` 重投该条通知）。

**企微（wechat）的结构性差异（T-43）**：加解密凭据是**企业级一套**
（token / EncodingAESKey / corpid），且载荷是**密文 XML**——"先解密才能知道是谁点了什么"，
故第 1 步在企微要先做一次企业级解密；此后（验签 → 幂等 → 角色授权 → 执行）与另外三家
**同一条路径、同一个出口**，`last_error`/原因键口径也一致。

**不含 HTTP**：入参是已解析的头/体，便于单测与复用（端点层只做取值与状态码透传）。
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from pilotstd.i18n import t

from ._credentials import SYSTEM_DEFAULT_USER_ID
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
from .wechat_crypto import WeChatCrypto, WeChatCryptoError, credentials_from, parse_plain_xml

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


def _resolve_target_by_actor(db: Any, user_name: str, credentials_for: Any) -> tuple[int, int] | None:
    """企微专用：由**通道侧用户标识**（`FromUserName` = 企微 userid）定位用户。

    **为什么企微不能复用 `_resolve_target`**：企微的加解密凭据是**企业级一套**
    （一个企业一个应用一个回调 URL），而四家渠道既有的取密钥口径是"按用户隔离"；
    企微回调里唯一稳定的通道侧身份是 `<FromUserName>`，故需要一次"企微 userid → 本地用户"反查。

    **为什么按 `users` 表逐行查而不写 SQL 条件**：`touser`（应用消息受众，与 `FromUserName`
    同口径）存放在 `user_credentials.credentials` 的**加密 JSON** 内，不是独立列 ⇒
    无法在 SQL 层过滤（反例：写 `WHERE touser = ?` 会因列不存在直接报错）。
    故只能逐用户调用既有的 `credentials_for(user_id, channel)`（**与另外三家同一取法**）
    再比对；候选集由 `users` 表给出，是**有界**且不随日志量增长的。

    **身份信任边界不变**：`FromUserName` 只用于"定位该用哪套密钥/哪条记录"，
    真正的信任仍来自验签（企业级 token/AESKey 只有企微服务器知道）+ DB 角色授权。
    """
    wanted = (user_name or "").strip()
    if not wanted:
        return None
    rows = db.fetchall("SELECT id FROM users ORDER BY id")
    candidates = [int(r["id"]) for r in rows]
    matched: int | None = None
    for candidate in candidates:
        creds = credentials_for(candidate, "wechat") or {}
        if str(creds.get("touser") or "").strip() == wanted:
            matched = candidate
            break
    # 只要没匹配到就退到唯一用户：单用户部署（本仓默认形态）里 `users` 仅一行，
    # 而"受众未填/填了别名"不应让回调整体失效——鉴权仍由后续验签 + DB 角色把关。
    if matched is None and len(candidates) == 1:
        matched = candidates[0]
    if matched is None:
        logger.warning("notification callback: wechat actor not mapped to a local user")
        return None
    log_rows = db.fetchall(
        "SELECT id FROM notification_log WHERE channel = ? AND status = ? ORDER BY id DESC LIMIT 1",
        ("wechat", "success"),
    )
    if not log_rows:
        return None
    return int(log_rows[0]["id"]), matched


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


def _parse_wechat_payload(
    channel: str, headers: dict[str, str], body: bytes, creds: dict[str, Any]
) -> dict[str, Any] | None:
    """企微：用**企业级三件套**解密 XML 回调体 → 明文消息 XML → 扁平字典。

    企微的载荷不是 JSON 而是 `<xml><Encrypt>…</Encrypt></xml>`，故**必须先解密**才能知道
    "是谁点了什么"（`FromUserName`/`EventKey`）；这与另外三家的"先读 JSON 再定位密钥"顺序相反，
    是本渠道的结构性差异（不是可以靠"少写一行"绕过的选择）。

    解密失败返回 `None`（调用方按 401 处理）；**不得容错放行**。
    """
    lowered = {k.lower(): v for k, v in headers.items()}
    token, encoding_aes_key, corpid = credentials_from(creds)
    if not (token and encoding_aes_key):
        logger.warning("notification callback: wechat credentials missing (token/encoding_aes_key)")
        return None
    try:
        crypto = WeChatCrypto(token, encoding_aes_key, corpid)
        plain_xml = crypto.decrypt_envelope(
            lowered.get("msg_signature", ""), lowered.get("timestamp", ""), lowered.get("nonce", ""), body
        )
    except WeChatCryptoError:
        # 原因不细分（签名错/密文非法/corpid 不匹配一律 401），且**不回显**给调用方
        logger.warning("notification callback: wechat payload rejected")
        return None
    parsed = parse_plain_xml(plain_xml)
    if not parsed:
        logger.warning("notification callback: wechat payload has no usable xml fields")
        return None
    return parsed


def handle_callback(
    db: Any,
    channel: str,
    headers: dict[str, str],
    body: bytes,
    credentials_for: Any,
    now: float | None = None,
    guard: Any = None,
    credentials: dict[str, Any] | None = None,
) -> CallbackOutcome:
    """处理一次渠道回调（完整闭环，见模块 docstring 的安全顺序）。

    `credentials`（可选）是调用方**已解析**的渠道凭据；目前只有企微会传
    （它的加解密凭据是**企业级一套**，不像另外三家按用户隔离）。
    为空时回落到 `credentials_for(user_id, channel)`（另外三家的既有路径）。
    """
    if channel == "wechat":
        # 企业级三件套：调用方给的优先，否则按默认用户读（单用户部署下即唯一一套）
        corp_creds: dict[str, Any] = credentials if credentials is not None else (
            credentials_for(SYSTEM_DEFAULT_USER_ID, channel) or {}
        )
        payload = _parse_wechat_payload(channel, headers, body, corp_creds)
        if payload is None:
            return _fail(STATUS_UNAUTHORIZED, "notification.callback.bad_signature")
    else:
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return _fail(STATUS_UNAUTHORIZED, "notification.callback.bad_signature")
        if not isinstance(payload, dict):
            return _fail(STATUS_UNAUTHORIZED, "notification.callback.bad_signature")

    envelope = parse_envelope(channel, payload, event_id="", now=now)
    if channel == "wechat":
        # 企微的按钮载荷里没有 `log_id:user_id`（企业级一套凭据）⇒ 由通道侧身份反查本地用户与记账行
        target = _resolve_target_by_actor(db, envelope.actor_ref, credentials_for)
    else:
        target = _resolve_target(db, channel, envelope.callback_data)
    if target is None:
        # 区分两类（阶段 3 · P5b 用户裁定）：
        #   ① **畸形/缺失 token** ⇒ 仍与验签失败同码（401）：不给攻击者一个可枚举的探针面；
        #   ② **格式合法但记录已不存在**（日志按保留策略清理后用户点了旧按钮）⇒ **410 优雅降级**，
        #      提示"操作已失效"，而不是 500/无响应，也不是语焉不详的"签名错误"。
        # 企微走 ①（其载荷里本就没有我们的 token，只有通道侧身份，故不存在"旧按钮"这一档）。
        if channel != "wechat" and _is_wellformed_token(envelope.callback_data):
            return _fail(STATUS_GONE, "notification.callback.action_expired")
        return _fail(STATUS_UNAUTHORIZED, "notification.callback.bad_signature")
    log_id, user_id = target

    # 取该用户该渠道的**解密**密钥：密钥本身不落库，解密失败即空字典 ⇒ 验签必然失败
    creds = credentials_for(user_id, channel) or {}
    secret = str(creds.get("secret") or "")
    # 企微是**三重组合**（token/EncodingAESKey/corpid），且签名覆盖的是密文本身 ⇒ 由 credentials 承载；
    # 另外三家沿用 `secret`（语义与调用口径完全不变）。
    verdict = verify_callback(
        channel, headers, body, secret, now, credentials=corp_creds if channel == "wechat" else None
    )
    if not verdict.ok:
        if channel == "wechat":
            # 企微的失败可能是"签名错/密文非法/corpid 不匹配/密钥未配置"四类之一；
            # 对外一律 401（不细分），但**日志必须留下线索**，否则线上只能靠抓包排查。
            logger.warning("notification callback: wechat verification failed (reason=%s)", verdict.reason_key)
        return _fail(verdict.status, verdict.reason_key)

    event_id = str(
        payload.get("event_id")
        or (payload.get("callback_query") or {}).get("id")
        or (payload.get("header") or {}).get("event_id")
        # 企微：`MsgId` + `CreateTime` 唯一标识一次事件（企微重投同一条 ⇒ 幂等拦截）
        or (
            f"wechat:{payload.get('MsgId')}:{payload.get('CreateTime')}"
            if channel == "wechat" and payload.get("MsgId")
            else ""
        )
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


def verify_wechat_url(
    headers: dict[str, str],
    echostr: str,
    credentials: dict[str, Any] | None = None,
    user_id: int = SYSTEM_DEFAULT_USER_ID,
    credentials_for: Any = None,
) -> str:
    """企微 **URL 验证（GET）**：验签 → 解密 `echostr` → 返回**明文**（响应体本体）。

    **为什么单独一个入口**：GET 验证没有"业务载荷"可分发，不需要走
    `handle_callback` 的幂等/授权/执行链路（那三段对"配置回调 URL"这一步毫无作用，
    硬塞进去只会让"谁点了什么"的分支污染一次纯粹的密钥确认）。
    端点据返回值直接以 `text/plain` 回显；失败返回空串 ⇒ 端点 401。

    `headers` 里必须携带 `msg_signature`/`timestamp`/`nonce`——企微把它们放在**查询串**，
    由端点层拼进 headers（服务层不解析 URL，保持"不含 HTTP"）。
    """
    creds: dict[str, Any] = credentials or {}
    if not creds and credentials_for is not None:
        creds = credentials_for(user_id, "wechat") or {}
    token, encoding_aes_key, corpid = credentials_from(creds)
    if not (token and encoding_aes_key):
        logger.warning("notification callback: wechat url verification without credentials")
        return ""
    lowered = {k.lower(): v for k, v in headers.items()}
    try:
        crypto = WeChatCrypto(token, encoding_aes_key, corpid)
        return crypto.verify_url(
            lowered.get("msg_signature", ""),
            lowered.get("timestamp", ""),
            lowered.get("nonce", ""),
            echostr,
        )
    except WeChatCryptoError:
        # 失败原因不细分、不回显（与 POST 路径同口径）
        logger.warning("notification callback: wechat url verification rejected")
        return ""
