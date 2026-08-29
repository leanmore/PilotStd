"""渠道子类 HTTP 响应/异常路径补测。
用 mock urlopen 覆盖 send() 中的 HTTP 状态码、错误响应、异常处理分支。
"""
import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from pilotstd.core.notification.channel import NotificationMessage


def _make_msg(title="Test", standard_number=""):
    return NotificationMessage(title=title, body="body", standard_number=standard_number)


# 各渠道模块的 urlopen 补丁路径
_DD_PATH = "pilotstd.core.notification.channels.dingtalk.urlopen"
_TG_PATH = "pilotstd.core.notification.channels.telegram.urlopen"
_FS_PATH = "pilotstd.core.notification.channels.feishu.urlopen"
_WX_PATH = "pilotstd.core.notification.channels.wechat.urlopen"


# ── DingTalk ──

class TestDingTalkSend:
    def test_empty_url_returns_false(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("")
        assert ch.send(_make_msg()) is False

    def test_validate_config(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        assert DingTalkChannel.validate_config({"webhook_url": "http://x"}) is True
        assert DingTalkChannel.validate_config({}) is False

    def test_send_success(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"errcode": 0}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_DD_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is True

    def test_send_with_standard_number(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"errcode": 0}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_DD_PATH, return_value=mock_resp) as mock_urlopen:
            assert ch.send(_make_msg(standard_number="GB/T 1")) is True
            call_args = mock_urlopen.call_args[0][0]
            body = json.loads(call_args.data.decode())
            assert "GB/T 1" in body["markdown"]["text"]

    def test_http_not_200(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__.return_value = mock_resp
        with patch(_DD_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is False

    def test_api_error_response(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"errcode": 1, "errmsg": "bad"}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_DD_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is False

    def test_send_exception(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("http://hook")
        with patch(_DD_PATH, side_effect=OSError("net down")):
            assert ch.send(_make_msg()) is False

    def test_sign_with_secret_produces_timestamp_and_sign(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("http://hook", secret="mysecret")
        result = ch._sign()
        assert "&timestamp=" in result
        assert "&sign=" in result

    def test_sign_without_secret_returns_empty(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("http://hook")
        assert ch._sign() == ""


# ── Telegram ──

class TestTelegramSend:
    def test_send_success(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"ok": True}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_TG_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is True

    def test_send_with_standard_number(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"ok": True}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_TG_PATH, return_value=mock_resp) as mock_urlopen:
            assert ch.send(_make_msg(standard_number="GB/T 1")) is True
            call_args = mock_urlopen.call_args[0][0]
            body = json.loads(call_args.data.decode())
            # 批次2（57f58a6c）去重契约：标准号已由构建器渲染进正文，
            # 发送层不再追加 standard_number（与 dingtalk 通道行为不同）
            assert "body" in body["text"]
            assert "GB/T 1" not in body["text"]

    def test_api_not_ok(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"ok": False, "description": "bad"}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_TG_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is False

    def test_http_not_200(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__.return_value = mock_resp
        with patch(_TG_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is False

    def test_http_404(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        with patch(_TG_PATH, side_effect=HTTPError(
            "http://x", 404, "Not Found", {}, None
        )):
            assert ch.send(_make_msg()) is False

    def test_http_401(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        with patch(_TG_PATH, side_effect=HTTPError(
            "http://x", 401, "Unauthorized", {}, None
        )):
            assert ch.send(_make_msg()) is False

    def test_http_500_error(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        with patch(_TG_PATH, side_effect=HTTPError(
            "http://x", 500, "Server Error", {}, None
        )):
            assert ch.send(_make_msg()) is False

    def test_general_exception(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        with patch(_TG_PATH, side_effect=ValueError("bad")):
            assert ch.send(_make_msg()) is False

    def test_send_with_empty_token_returns_false(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("", "")
        assert ch.send(_make_msg()) is False

    def test_validate_config(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        assert TelegramChannel.validate_config({"bot_token": "x", "chat_id": "1"}) is True
        assert TelegramChannel.validate_config({}) is False

    def test_log_dedup_suppresses_duplicate(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        ch._log_dedup("test error")
        ch._log_dedup("test error")  # 120s 内重复，抑制

    def test_log_dedup_allows_different(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("tok", "123")
        ch._log_dedup("error A")
        ch._log_dedup("error B")  # 不同消息，不抑制


# ── Feishu ──

class TestFeishuSend:
    def test_empty_url_returns_false(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        ch = FeishuChannel("")
        assert ch.send(_make_msg()) is False

    def test_validate_config(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        assert FeishuChannel.validate_config({"webhook_url": "http://x"}) is True
        assert FeishuChannel.validate_config({}) is False

    def test_send_success(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        ch = FeishuChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"code": 0}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_FS_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is True

    def test_send_with_standard_number(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        ch = FeishuChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"code": 0}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_FS_PATH, return_value=mock_resp) as mock_urlopen:
            assert ch.send(_make_msg(standard_number="GB/T 1")) is True
            call_args = mock_urlopen.call_args[0][0]
            body = json.loads(call_args.data.decode())
            card_elements = body["card"]["elements"]
            found = any("GB/T 1" in e.get("content", "") for e in card_elements)
            assert found

    def test_api_error_response(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        ch = FeishuChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"code": 1, "msg": "bad"}).encode()
        mock_resp.__enter__.return_value = mock_resp
        with patch(_FS_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is False

    def test_http_not_200(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        ch = FeishuChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__.return_value = mock_resp
        with patch(_FS_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is False

    def test_send_exception(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        ch = FeishuChannel("http://hook")
        with patch(_FS_PATH, side_effect=OSError("net down")):
            assert ch.send(_make_msg()) is False


# ── Wechat ──

class TestWechatSend:
    def test_send_success(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        ch = WechatChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        with patch(_WX_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is True

    def test_send_with_standard_number(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        ch = WechatChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        with patch(_WX_PATH, return_value=mock_resp) as mock_urlopen:
            assert ch.send(_make_msg(standard_number="GB/T 1")) is True
            call_args = mock_urlopen.call_args[0][0]
            body = json.loads(call_args.data.decode())
            assert "GB/T 1" in body["markdown"]["content"]

    def test_http_not_200(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        ch = WechatChannel("http://hook")
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__.return_value = mock_resp
        with patch(_WX_PATH, return_value=mock_resp):
            assert ch.send(_make_msg()) is False

    def test_send_exception(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        ch = WechatChannel("http://hook")
        with patch(_WX_PATH, side_effect=OSError("net down")):
            assert ch.send(_make_msg()) is False

    def test_empty_url_returns_false(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        ch = WechatChannel("")
        assert ch.send(_make_msg()) is False

    def test_validate_config(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        assert WechatChannel.validate_config({"webhook_url": "http://x"}) is True
        assert WechatChannel.validate_config({}) is False


# ── Channel 接口 (channel.py) ──

class TestChannelABC:
    def test_validate_config_default(self):
        # v1.1：规范基类位于 channels.base（channel.py 旧名已废弃转发）
        from pilotstd.core.notification.channels.base import NotificationChannel
        assert NotificationChannel.validate_config({}) is True

    def test_message_repr(self):
        from pilotstd.core.notification.channel import NotificationMessage
        msg = NotificationMessage(title="T", body="B")
        assert "NotificationMessage" in repr(msg)
        assert "T" in repr(msg)
