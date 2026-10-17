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
from typing import Any, Iterable, Protocol

from .wechat_crypto import WeChatCrypto, WeChatCryptoError, credentials_from, extract_encrypt

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
# 410：按钮对应记录已不存在（如日志按保留策略被清理）⇒ **优雅降级**，与鉴权失败区分。
# 依据：阶段 3 · P5b 用户裁定——"未成功回填/已失效的按钮点击时应给出可读提示，
# 而不是抛 500 或无响应"。畸形/缺失 token 仍按 401（避免变成可探测的枚举面）。
STATUS_GONE = 410
STATUS_UNSUPPORTED = 501


@dataclass(frozen=True)
class SignatureVerdict:
    """验签结论：`ok` + 对外状态码 + 原因键（原因键只进日志，不回给调用方）。"""

    ok: bool
    status: int
    reason_key: str = ""


class ActionVerdictLike(Protocol):
    """`SignatureVerdict` 的结构性子集：授权结论只需要 `ok` / `status` / `reason_key`。

    成员声明为**只读属性**：`SignatureVerdict` 是 frozen dataclass，字段本身只读，
    声明成可写变量会让 mypy 报"expected settable variable, got read-only attribute"。
    """

    @property
    def ok(self) -> bool: ...

    @property
    def status(self) -> int: ...

    @property
    def reason_key(self) -> str: ...


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


def _verify_wechat(
    headers: dict[str, str],
    body: bytes,
    credentials: dict[str, Any] | None,
) -> SignatureVerdict:
    """企微支的验签（自 `verify_callback` 拆出，守 G-010 的单函数逻辑行上限）。

    **为什么读 `credentials` 而不是 `secret`**：企微回调是**三件套**
    （`token` / `encoding_aes_key` / `corpid`），不是单一共享密钥；且请求体是**密文 XML**，
    签名覆盖的是密文本身而非"报文哈希"。故该支只从 `credentials` 取参数，
    对 `secret` 不敏感（另外三家的用法与语义**完全不变**）。
    验签失败的**原因不细分**：一律 401（与另外三家同口径，不给探测者反馈）。
    """
    # 三件套缺一即拒（与"缺密钥 401"同口径，不回显缺了哪一件）
    if credentials is None:
        return _verdict(False, "notification.callback.secret_missing", STATUS_UNAUTHORIZED)
    token, encoding_aes_key, corpid = credentials_from(credentials)
    if not (token and encoding_aes_key):
        return _verdict(False, "notification.callback.secret_missing", STATUS_UNAUTHORIZED)
    msg_signature = headers.get("msg_signature", "")
    timestamp = headers.get("timestamp", "")
    nonce = headers.get("nonce", "")
    if not (msg_signature and timestamp and nonce):
        return _verdict(False, "notification.callback.bad_signature", STATUS_UNAUTHORIZED)
    try:
        crypto = WeChatCrypto(token, encoding_aes_key, corpid)
    except WeChatCryptoError:
        # 密钥非法（非 base64 / 长度不对）：属凭证层问题，等同"密钥缺失"
        return _verdict(False, "notification.callback.secret_missing", STATUS_UNAUTHORIZED)
    # 签名输入的取值位置按请求形态分派：
    # · POST（有请求体）⇒ XML 里的 <Encrypt>，取不到密文即无法验签 ⇒ 拒绝；
    # · GET（URL 验证）⇒ 查询参数 echostr（企微把它放在查询串，由端点层搬进 headers）。
    try:
        signed_payload = extract_encrypt(body) if body else headers.get("echostr", "")
    except WeChatCryptoError:
        return _verdict(False, "notification.callback.bad_signature", STATUS_UNAUTHORIZED)
    if crypto.check_signature(msg_signature, timestamp, nonce, signed_payload):
        return _verdict(True, "", STATUS_OK)
    return _verdict(False, "notification.callback.bad_signature", STATUS_UNAUTHORIZED)


def verify_callback(
    channel: str,
    headers: dict[str, str],
    body: bytes,
    secret: str,
    now: float | None = None,
    credentials: dict[str, Any] | None = None,
) -> SignatureVerdict:
    """逐渠道验签（渠道无关入口）。

    已实现的渠道：`telegram`（`X-Telegram-Bot-Api-Secret-Token` 共享密钥头）、
    `dingtalk`（`timestamp` + `sign`，HMAC-SHA256(secret, "timestamp\nsecret") 的 base64）、
    `feishu`（`X-Lark-Signature` = sha256(timestamp + nonce + encrypt_key + body)）、
    `wechat`（企业微信 `msg_signature` = sha1(token, timestamp, nonce, encrypt)，**XML + AES**；
    参数来源与拒绝口径见 `_verify_wechat`）。

    验签失败的**原因不细分**：一律 401（不给探测者反馈）。
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

    if channel == "wechat":
        return _verify_wechat(lowered, body, credentials)

    # 其它：能力未启用/未取证，直接拒绝（不猜协议）
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

    渠道载荷结构差异大（TG `callback_query.data`、钉钉 `action`+`outTrackId`、飞书 `action.value`、
    企微**解密后的消息 XML** 的 `EventKey`/`Content`），这里按**我们下发的 `callback_data`** 取值；
    取不到时返回空动作，由调用方按未知动作拒绝。

    `wechat` 的输入是 `wechat_crypto.parse_plain_xml` 得到的扁平字典（XML 字段名 → 文本）。
    **字段依据来自可运行的参考实现**（本地副本 `D:/mp插件/MoviePilot-src/app/modules/wechat/__init__.py:179-207`）：

    * `MsgType=event` **且** `Event=click` ⇒ 取 **`EventKey`**（该实现注释明写「event 事件只有
      `click` 才有效，`enter_agent` 无效」）；
    * `MsgType=text` ⇒ 取 **`Content`**（用户直接发消息当命令，同一实现 :204-207 即如此）；
    * 其余 `MsgType`/`Event` **一律不产生动作**（宁可忽略，也不把未取证形态当成命令解析）。

    ⚠️ 2026-10-17 修正：本分支此前**优先取 `TaskId`**，那是照文档推断的字段，**参考实现里没有
    任何依据**（它只认 `EventKey`）⇒ 已移除；若将来另拿到"模板卡片按钮回调"的真报文再按实证加回。
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
    elif channel == "wechat":
        msg_type = str(payload.get("MsgType") or "").strip().lower()
        event = str(payload.get("Event") or "").strip().lower()
        raw_data = ""
        if msg_type == "event" and event == "click":
            # 企微"用户点菜单/按钮"的实证形态：菜单 click 事件把我们的键放在 EventKey
            raw_data = str(payload.get("EventKey") or "")
        elif msg_type == "text":
            # 用户直接给我们发消息：正文即命令（与参考实现同口径）
            raw_data = str(payload.get("Content") or "")
        action, callback_data = _split_action(raw_data)
        actor_ref = str(payload.get("FromUserName") or "")
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
