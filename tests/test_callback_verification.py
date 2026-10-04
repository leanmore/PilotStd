"""阶段 B（B2a）：回调验签骨架、动作授权、防重放/幂等。

设计依据：[03-实施路径.md](../../docs/plans/notification-redesign/03-实施路径.md) §3.4 验证方式
（"① 验签单测：每渠道'正确签名通过 / 错签名 401 / 重放 200 幂等'（共 12 例）；
② 动作单测：retry/ignore/snooze + 越权拒绝"）。
"""

import base64
import hashlib
import hmac
import json

from pilotstd.core.notification.callback import (
    ACTION_IGNORE,
    ACTION_RETRY,
    ACTION_SNOOZE,
    STATUS_FORBIDDEN,
    STATUS_OK,
    STATUS_UNAUTHORIZED,
    STATUS_UNSUPPORTED,
    ReplayGuard,
    authorize_action,
    parse_envelope,
    verify_callback,
)

NOW = 1_700_000_000.0
SECRET = "s3cr3t"


def _dingtalk_headers(secret: str = SECRET, stamp_ms: str | None = None) -> dict[str, str]:
    stamp = stamp_ms or str(int(NOW * 1000))
    raw = hmac.new(secret.encode(), f"{stamp}\n{secret}".encode(), hashlib.sha256).digest()
    return {"timestamp": stamp, "sign": base64.b64encode(raw).decode()}


def _feishu_headers(secret: str = SECRET, body: bytes = b"{}", stamp: str | None = None) -> dict[str, str]:
    ts = stamp or str(int(NOW))
    nonce = "n1"
    digest = hashlib.sha256((ts + nonce + secret).encode() + body).hexdigest()
    return {
        "X-Lark-Request-Timestamp": ts,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": digest,
    }


class TestVerifyPerChannel:
    """每渠道：正确签名通过 / 错签名 401 / 重放幂等（共 12 例的前 9 例）。"""

    def test_telegram_correct_signature_passes(self):
        verdict = verify_callback(
            "telegram", {"X-Telegram-Bot-Api-Secret-Token": SECRET}, b"{}", SECRET, NOW
        )
        assert verdict.ok is True and verdict.status == STATUS_OK

    def test_telegram_wrong_signature_401(self):
        verdict = verify_callback(
            "telegram", {"X-Telegram-Bot-Api-Secret-Token": "nope"}, b"{}", SECRET, NOW
        )
        assert verdict.ok is False and verdict.status == STATUS_UNAUTHORIZED

    def test_telegram_replay_is_idempotent(self):
        guard = ReplayGuard()
        assert guard.admit("tg-1", NOW) is True
        # 重放仍返回 200（渠道不该重投），但动作**不重复执行**
        verdict = verify_callback(
            "telegram", {"X-Telegram-Bot-Api-Secret-Token": SECRET}, b"{}", SECRET, NOW
        )
        assert verdict.status == STATUS_OK
        assert guard.admit("tg-1", NOW + 1) is False

    def test_dingtalk_correct_signature_passes(self):
        verdict = verify_callback("dingtalk", _dingtalk_headers(), b"{}", SECRET, NOW)
        assert verdict.ok is True and verdict.status == STATUS_OK

    def test_dingtalk_wrong_signature_401(self):
        headers = _dingtalk_headers(secret="other")
        verdict = verify_callback("dingtalk", headers, b"{}", SECRET, NOW)
        assert verdict.ok is False and verdict.status == STATUS_UNAUTHORIZED

    def test_dingtalk_replay_is_idempotent(self):
        guard = ReplayGuard()
        assert guard.admit("dd-1", NOW) is True
        verdict = verify_callback("dingtalk", _dingtalk_headers(), b"{}", SECRET, NOW)
        assert verdict.status == STATUS_OK
        assert guard.admit("dd-1", NOW + 1) is False

    def test_feishu_correct_signature_passes(self):
        body = b'{"action": {}}'
        verdict = verify_callback("feishu", _feishu_headers(body=body), body, SECRET, NOW)
        assert verdict.ok is True and verdict.status == STATUS_OK

    def test_feishu_wrong_signature_401(self):
        body = b'{"action": {}}'
        headers = _feishu_headers(body=body)
        headers["X-Lark-Signature"] = "0" * 64
        verdict = verify_callback("feishu", headers, body, SECRET, NOW)
        assert verdict.ok is False and verdict.status == STATUS_UNAUTHORIZED

    def test_feishu_replay_is_idempotent(self):
        guard = ReplayGuard()
        body = b'{"action": {}}'
        assert guard.admit("fs-1", NOW) is True
        verdict = verify_callback("feishu", _feishu_headers(body=body), body, SECRET, NOW)
        assert verdict.status == STATUS_OK
        assert guard.admit("fs-1", NOW + 1) is False


class TestVerifyEdgeCases:
    """验签的边界：企微未启用、缺密钥、时间戳过期/非法。"""

    def test_wechat_unsupported_501(self):
        verdict = verify_callback("wechat", {}, b"{}", SECRET, NOW)
        assert verdict.ok is False and verdict.status == STATUS_UNSUPPORTED

    def test_missing_secret_rejects(self):
        for channel, headers in (
            ("telegram", {"X-Telegram-Bot-Api-Secret-Token": ""}),
            ("dingtalk", _dingtalk_headers()),
            ("feishu", _feishu_headers()),
        ):
            verdict = verify_callback(channel, headers, b"{}", "", NOW)
            assert verdict.status == STATUS_UNAUTHORIZED, channel

    def test_stale_and_invalid_timestamps_reject(self):
        old = str(int((NOW - 7200) * 1000))
        stale = verify_callback("dingtalk", _dingtalk_headers(stamp_ms=old), b"{}", SECRET, NOW)
        assert stale.status == STATUS_UNAUTHORIZED
        bad = {"timestamp": "abc", "sign": "x"}
        assert verify_callback("dingtalk", bad, b"{}", SECRET, NOW).status == STATUS_UNAUTHORIZED
        no_headers = verify_callback("feishu", {"X-Lark-Signature": "x"}, b"{}", SECRET, NOW)
        assert no_headers.status == STATUS_UNAUTHORIZED

    def test_feedback_does_not_leak_reason(self):
        """验签失败不区分"签名错"与"缺字段"（避免给探测者反馈）——仅状态码一致。"""
        wrong = verify_callback("telegram", {"X-Telegram-Bot-Api-Secret-Token": "x"}, b"{}", SECRET, NOW)
        empty = verify_callback("telegram", {}, b"{}", SECRET, NOW)
        assert (wrong.status, empty.status) == (STATUS_UNAUTHORIZED, STATUS_UNAUTHORIZED)


class TestAuthorizeAction:
    """动作授权：仅管理员；未知动作拒绝（不信任回调载荷里的身份）。"""

    def test_admin_allowed_for_all_actions(self):
        for action in (ACTION_RETRY, ACTION_IGNORE, ACTION_SNOOZE):
            verdict = authorize_action("admin", action)
            assert verdict.ok is True and verdict.status == STATUS_OK, action

    def test_non_admin_forbidden(self):
        for action in (ACTION_RETRY, ACTION_IGNORE, ACTION_SNOOZE):
            verdict = authorize_action("user", action)
            assert verdict.ok is False and verdict.status == STATUS_FORBIDDEN, action

    def test_unknown_action_forbidden(self):
        assert authorize_action("admin", "drop_database").status == STATUS_FORBIDDEN


class TestReplayGuard:
    """防重放：窗口内只放行一次；窗口外放行；空事件号不放行。"""

    def test_window_behaviour(self):
        guard = ReplayGuard(window_seconds=60.0)
        assert guard.admit("e1", NOW) is True
        assert guard.admit("e1", NOW + 59) is False
        assert guard.admit("e1", NOW + 61) is True

    def test_empty_event_id_never_admitted(self):
        assert ReplayGuard().admit("", NOW) is False

    def test_prune_keeps_store_small(self):
        guard = ReplayGuard(window_seconds=10.0)
        for i in range(5):
            guard.admit(f"e{i}", NOW + i)
        guard.admit("fresh", NOW + 40)
        assert len(guard) == 1  # 过期条目被清理


class TestParseEnvelope:
    """载荷归一：只取字段，不做信任判断。"""

    def test_telegram_callback_query(self):
        payload = {"callback_query": {"data": "retry:tok-1", "from": {"id": 7}}}
        env = parse_envelope("telegram", payload, event_id="e1", now=NOW)
        assert (env.action, env.callback_data, env.actor_ref) == (ACTION_RETRY, "tok-1", "7")

    def test_dingtalk_action_and_track(self):
        env = parse_envelope("dingtalk", {"action": "ignore", "outTrackId": "t-1", "userId": "u1"}, now=NOW)
        assert (env.action, env.callback_data, env.actor_ref) == (ACTION_IGNORE, "t-1", "u1")

    def test_feishu_action_value(self):
        payload = {"action": {"value": {"action": "snooze", "token": "tok-2"}}, "operator": {"open_id": "o1"}}
        env = parse_envelope("feishu", payload, now=NOW)
        assert (env.action, env.callback_data, env.actor_ref) == (ACTION_SNOOZE, "tok-2", "o1")

    def test_unknown_action_left_empty(self):
        env = parse_envelope("telegram", {"callback_query": {"data": "boom:tok"}}, now=NOW)
        assert env.action == ""  # 由调用方按未知动作拒绝

    def test_non_json_payload_does_not_raise(self):
        env = parse_envelope("telegram", json.loads("{}"), now=NOW)
        assert env.action == ""
