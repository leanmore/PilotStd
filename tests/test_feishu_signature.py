"""飞书渠道签名（大阶段 5）：实现此前"字段声明未实现"的签名校验密钥。"""

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import patch

from pilotstd.core.notification.channel import NotificationMessage
from pilotstd.core.notification.channels.feishu import FeishuChannel


class _Resp:
    """真实上下文管理器替身（`with` 按类型查找 `__enter__`）。"""

    status = 200

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _msg() -> NotificationMessage:
    return NotificationMessage(title="标题", body="正文")


def _expected_sign(secret: str, timestamp: str) -> str:
    """按官方口径独立复算（测试不复用实现里的函数）。"""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


class TestFeishuSignature:
    def test_signature_matches_documented_algorithm(self):
        sent: dict = {}

        def _capture(req, timeout=10):  # noqa: ARG001 - 契约签名
            sent.update(json.loads(req.data.decode("utf-8")))
            return _Resp({"code": 0})

        channel = FeishuChannel(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/x", secret="s3cr3t")
        with patch("pilotstd.core.notification.channels.feishu.urlopen", side_effect=_capture):
            assert channel.send(_msg()) is True

        assert set(sent) >= {"timestamp", "sign", "msg_type", "card"}
        assert sent["sign"] == _expected_sign("s3cr3t", sent["timestamp"])

    def test_timestamp_is_seconds_and_changes_signature(self):
        sent: dict = {}

        def _capture(req, timeout=10):  # noqa: ARG001 - 契约签名
            sent.update(json.loads(req.data.decode("utf-8")))
            return _Resp({"code": 0})

        channel = FeishuChannel(webhook_url="https://x", secret="s3cr3t")
        with patch("pilotstd.core.notification.channels.feishu.urlopen", side_effect=_capture):
            channel.send(_msg())
        first = dict(sent)
        with (
            patch("pilotstd.core.notification.channels.feishu.urlopen", side_effect=_capture),
            patch.object(time, "time", return_value=time.time() + 2),
        ):
            channel.send(_msg())

        assert sent["timestamp"] != first["timestamp"]
        assert sent["sign"] != first["sign"]
        assert sent["sign"] == _expected_sign("s3cr3t", sent["timestamp"])

    def test_no_secret_keeps_request_body_unchanged(self):
        sent: dict = {}

        def _capture(req, timeout=10):  # noqa: ARG001 - 契约签名
            sent.update(json.loads(req.data.decode("utf-8")))
            return _Resp({"code": 0})

        channel = FeishuChannel(webhook_url="https://x")
        with patch("pilotstd.core.notification.channels.feishu.urlopen", side_effect=_capture):
            assert channel.send(_msg()) is True

        assert set(sent) == {"msg_type", "card"}, "未配密钥时请求体必须与既有行为逐字一致"

    def test_dingtalk_and_feishu_algorithms_differ(self):
        """两家的 HMAC 布局互换，防止日后"顺手统一"造成静默失效。"""
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        secret = "same-secret"
        dd = DingTalkChannel(webhook_url="https://x", secret=secret)
        dd_url_suffix = dd._sign()
        # 钉钉签名在 URL 上（timestamp 为毫秒），飞书在请求体里（秒）
        assert "timestamp=" in dd_url_suffix and "sign=" in dd_url_suffix
        fs = FeishuChannel(webhook_url="https://x", secret=secret)._sign()
        assert set(fs) == {"timestamp", "sign"}
        assert fs["sign"] == _expected_sign(secret, fs["timestamp"])
