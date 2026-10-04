"""回调验签与动作授权骨架（阶段 B 的渠道无关底座）。

设计依据：[03-实施路径.md](../../../docs/plans/notification-system-design/../notification-redesign/03-实施路径.md) §3.4
与 [02-framework-update.md](../../../docs/plans/notification-system-design/02-framework-update.md) §2.3
"基础先行：先做渠道无关的公共能力（改写句柄抽象、**回调端点骨架、验签骨架**）"。

**本模块不含公网端点**（`POST /api/notification/callback/{channel}` 属 B2b，需要部署侧确定
对外可达地址与 TLS）。这里只放三件可独立验证的事：

1. **逐渠道验签**（`verify_callback`）：常量时间比较 + 时间戳新鲜度窗口；
2. **动作授权**（`authorize_action`）：只认**服务端解析出的角色**，绝不信任回调载荷里的身份
   （设计 §3.4 风险 ①"动作执行必须重新鉴权（不信任 `callback_data` 里的身份）"）；
3. **防重放/幂等**（`ReplayGuard`）：同一事件第二次到达不得再执行动作。

安全口径：
- 任何验签失败一律 401，且**不区分**"签名错"与"缺字段"（避免给探测者反馈）；
- 比较用 `hmac.compare_digest`（常量时间），不做短路字符串比较；
- 时间戳超出窗口即拒绝（`_MAX_SKEW_SECONDS`），窗口内的重复投递交给 `ReplayGuard`。
"""

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Iterable

# 三个低频动作（设计 §1.2 B 行："低频编辑（状态/回执/汇总）"配套的用户动作）
ACTION_RETRY = "retry"
ACTION_IGNORE = "ignore"
ACTION_SNOOZE = "snooze"
SUPPORTED_ACTIONS = (ACTION_RETRY, ACTION_IGNORE, ACTION_SNOOZE)

# 动作用户必须是管理员（设计 §3.4 验证方式 ②："非管理员发 retry → 403"）
ACTION_REQUIRED_ROLE = "admin"

# 时间戳新鲜度窗口（秒）：钉钉回调规范为 1 小时
_MAX_SKEW_SECONDS = 3600.0

# 幂等窗口（秒）：覆盖渠道可能的重投（Telegram 重试 24h 内、钉钉 3 次重投）
_REPLAY_WINDOW_SECONDS = 86400.0

# 验签失败/不支持时的对外状态码（不区分具体原因）
STATUS_OK = 200
STATUS_UNAUTHORIZED = 401
STATUS_FORBIDDEN = 403
STATUS_UNSUPPORTED = 501


@dataclass(frozen=True)
class SignatureVerdict:
    """验签结论：`ok` + 对外状态码 + 原因键（原因键只进日志，不回给调用方）。"""

    ok: bool
    status: int
    reason_key: str = ""


@dataclass(frozen=True)
class CallbackEnvelope:
    """回调载荷的**已验签**摘要。

    `actor_ref` 是渠道侧给的身份线索，**不可信**：动作鉴权必须用服务端解析出的角色
    （`authorize_action` 的入参），不得用这里的值。
    """

    channel: str
    action: str
    callback_data: str
    event_id: str
    actor_ref: str = ""
    timestamp: float = 0.0


def _hmac_b64(secret: str, payload: str, digest: str = "sha256") -> str:
    """HMAC(digest, secret, payload) → base64（钉钉回调/加签同款口径）。"""
    raw = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), digest).digest()
    return base64.b64encode(raw).decode("utf-8")


def _fresh(timestamp: float, now: float) -> bool:
    """时间戳是否在新鲜度窗口内。"""
    return 0.0 < timestamp and abs(now - timestamp) <= _MAX_SKEW_SECONDS


def _verdict(ok: bool, reason_key: str, status: int) -> SignatureVerdict:
    return SignatureVerdict(ok=ok, status=status, reason_key=reason_key)


def verify_callback(
    channel: str,
    headers: dict[str, str],
    body: bytes,
    secret: str,
    now: float | None = None,
) -> SignatureVerdict:
    """逐渠道验签（渠道无关入口）。

    已实现的渠道：`telegram`（`X-Telegram-Bot-Api-Secret-Token` 共享密钥头）、
    `dingtalk`（`timestamp` + `sign`，HMAC-SHA256(secret, "timestamp\nsecret") 的 base64）、
    `feishu`（`X-Lark-Signature` = sha256(timestamp + nonce + encrypt_key + body)）。
    `wechat` 依能力调查缺口 1/2 **未取证**，此处一律拒绝（501），不猜协议。
    """
    current = time.time() if now is None else now
    lowered = {k.lower(): v for k, v in headers.items()}

    if channel == "telegram":
        if not secret:
            return _verdict(False, "notification.callback.secret_missing", STATUS_UNAUTHORIZED)
        provided = lowered.get("x-telegram-bot-api-secret-token", "")
        if provided and hmac.compare_digest(provided, secret):
            return _verdict(True, "", STATUS_OK)
        return _verdict(False, "notification.callback.bad_signature", STATUS_UNAUTHORIZED)

    if channel == "dingtalk":
        if not secret:
            return _verdict(False, "notification.callback.secret_missing", STATUS_UNAUTHORIZED)
        raw_ts = lowered.get("timestamp", "")
        provided = lowered.get("sign", "")
        try:
            stamp = float(raw_ts) / 1000.0  # 钉钉为毫秒
        except (TypeError, ValueError):
            return _verdict(False, "notification.callback.bad_timestamp", STATUS_UNAUTHORIZED)
        if not _fresh(stamp, current):
            return _verdict(False, "notification.callback.stale_timestamp", STATUS_UNAUTHORIZED)
        expected = _hmac_b64(secret, f"{raw_ts}\n{secret}")
        if provided and hmac.compare_digest(provided, expected):
            return _verdict(True, "", STATUS_OK)
        return _verdict(False, "notification.callback.bad_signature", STATUS_UNAUTHORIZED)

    if channel == "feishu":
        if not secret:
            return _verdict(False, "notification.callback.secret_missing", STATUS_UNAUTHORIZED)
        # 变量名与钉钉分支隔离：同名会让 mypy 跨分支串味（float + str）
        lark_stamp = lowered.get("x-lark-request-timestamp", "")
        nonce = lowered.get("x-lark-request-nonce", "")
        provided = lowered.get("x-lark-signature", "")
        try:
            stamp_value = float(lark_stamp)
        except (TypeError, ValueError):
            return _verdict(False, "notification.callback.bad_timestamp", STATUS_UNAUTHORIZED)
        if not _fresh(stamp_value, current):
            return _verdict(False, "notification.callback.stale_timestamp", STATUS_UNAUTHORIZED)
        digest = hashlib.sha256(
            (lark_stamp + nonce + secret).encode("utf-8") + body
        ).hexdigest()
        if provided and hmac.compare_digest(provided, digest):
            return _verdict(True, "", STATUS_OK)
        return _verdict(False, "notification.callback.bad_signature", STATUS_UNAUTHORIZED)

    # wechat 及其它：能力未启用/未取证，直接拒绝（不猜协议）
    return _verdict(False, "notification.callback.channel_unsupported", STATUS_UNSUPPORTED)


def authorize_action(role: str, action: str) -> SignatureVerdict:
    """动作授权：仅管理员可执行三个动作。

    `role` 必须是**服务端**解析出的角色（来自会话/用户表），**不得**取回调载荷里的身份。
    """
    if action not in SUPPORTED_ACTIONS:
        return _verdict(False, "notification.callback.action_unknown", STATUS_FORBIDDEN)
    if role != ACTION_REQUIRED_ROLE:
        return _verdict(False, "notification.callback.forbidden", STATUS_FORBIDDEN)
    return _verdict(True, "", STATUS_OK)


@dataclass
class ReplayGuard:
    """防重放/幂等：同一 `event_id` 在窗口内只放行一次。

    默认**进程内**实现（uvicorn 单 worker 部署成立）；接口留成类，便于换成 DB/Redis 实现
    （跨进程/重启后仍幂等）——换实现属 B2b 范围。
    """

    window_seconds: float = _REPLAY_WINDOW_SECONDS
    _seen: dict[str, float] = field(default_factory=dict)

    def admit(self, event_id: str, now: float | None = None) -> bool:
        """返回 True 表示首次到达（可执行动作）；False 表示窗口内已处理过。"""
        if not event_id:
            return False
        current = time.time() if now is None else now
        self._prune(current)
        last = self._seen.get(event_id)
        if last is not None and current - last <= self.window_seconds:
            return False
        self._seen[event_id] = current
        return True

    def _prune(self, now: float) -> None:
        expired = [k for k, ts in self._seen.items() if now - ts > self.window_seconds]
        for key in expired:
            del self._seen[key]

    def __len__(self) -> int:  # 便于观测与测试
        return len(self._seen)


def parse_envelope(channel: str, payload: dict, event_id: str = "", now: float | None = None) -> CallbackEnvelope:
    """把各渠道的载荷归一为 `CallbackEnvelope`（只读字段，不做信任判断）。

    渠道载荷结构差异大（TG `callback_query.data`、钉钉 `action`+`outTrackId`、飞书 `action.value`），
    这里按**我们下发的 `callback_data`** 取值；取不到时返回空动作，由调用方按未知动作拒绝。
    """
    current = time.time() if now is None else now
    action = ""
    callback_data = ""
    actor_ref = ""
    if channel == "telegram":
        query = payload.get("callback_query") or {}
        callback_data = str(query.get("data") or "")
        actor_ref = str((query.get("from") or {}).get("id") or "")
        action, callback_data = _split_action(callback_data)
    elif channel == "dingtalk":
        action = str(payload.get("action") or "")
        callback_data = str(payload.get("outTrackId") or "")
        actor_ref = str(payload.get("userId") or "")
    elif channel == "feishu":
        action_block = payload.get("action") or {}
        action = str(action_block.get("value", {}).get("action") or "")
        callback_data = str(action_block.get("value", {}).get("token") or "")
        actor_ref = str((payload.get("operator") or {}).get("open_id") or "")
    return CallbackEnvelope(
        channel=channel,
        action=action,
        callback_data=callback_data,
        event_id=event_id,
        actor_ref=actor_ref,
        timestamp=current,
    )


def _split_action(data: str) -> tuple[str, str]:
    """我们下发的 `callback_data` 形如 `action:token`；拆不出动作则返回空动作。"""
    if ":" not in data:
        return "", data
    head, _, tail = data.partition(":")
    return (head if head in SUPPORTED_ACTIONS else ""), tail


def envelope_summary(envelope: CallbackEnvelope, actions: Iterable[str] = SUPPORTED_ACTIONS) -> str:
    """日志用的最小摘要：**不含**载荷原文（回调可能带用户内容）。"""
    return f"channel={envelope.channel} action={envelope.action} known={envelope.action in tuple(actions)}"
