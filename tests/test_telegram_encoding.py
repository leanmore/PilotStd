"""Telegram 发送编码回归：中文必须以 UTF-8 原文发送，不能发 \\uXXXX 转义。"""

from unittest.mock import MagicMock, patch

from pilotstd.core.notification.channels.telegram import TelegramChannel


def test_telegram_payload_is_utf8_not_escaped():
    channel = TelegramChannel("1:token", "42")
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'{"ok": true}'
    with patch("pilotstd.core.notification.channels.telegram.requests.post") as post:
        post.return_value = resp
        ok, _retryable = channel._post_once("中文测试：标准库 GB/T 19001-2016 📦")
    assert ok is True
    _, kwargs = post.call_args
    body = kwargs["data"].decode("utf-8")
    assert "中文测试" in body
    assert "\\u4e2d" not in body
    assert kwargs["headers"]["Content-Type"] == "application/json; charset=utf-8"
