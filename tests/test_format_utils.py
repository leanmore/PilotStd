"""core/notification/_format_utils.py 补测。"""
from unittest.mock import MagicMock, patch

from pilotstd.core.notification._format_utils import (
    do_test_send,
    format_standard_status_changed_aggregated,
)
from tests.fixtures.engine_mock_tree import ChannelStub, ConfigStub


def _make_entry(num, new_status="现行", old_status="现行"):
    msg = MagicMock()
    msg.standard_number = f"GB/T {num}"
    msg.standard_name = f"标准{num}"
    msg.new_status = new_status
    msg.old_status = old_status
    msg.changed_at = "2026-01-15T10:30:00+08:00"
    return (msg, "channel", "2026-01-15")


class TestFormatAggregated:
    def test_single_entry(self):
        entries = [_make_entry(1)]
        result = format_standard_status_changed_aggregated("", entries, 1)
        assert "GB/T 1" in result
        assert "标准1" in result

    def test_expired_count_in_header(self):
        entries = [_make_entry(1, new_status="废止")]
        result = format_standard_status_changed_aggregated("", entries, 1)
        assert "废止" in result

    def test_multiple_entries_under_10(self):
        entries = [_make_entry(i) for i in range(5)]
        result = format_standard_status_changed_aggregated("", entries, 5)
        assert "5 项" in result

    def test_over_10_entries_truncated(self):
        entries = [_make_entry(i) for i in range(15)]
        result = format_standard_status_changed_aggregated("", entries, 15)
        assert "等 5 项" in result

    def test_missing_name_and_changed_at(self):
        # 无 standard_name 且无 changed_at 的边界路径
        msg = MagicMock()
        msg.standard_number = "X"
        msg.standard_name = ""
        msg.new_status = "现行"
        msg.old_status = "现行"
        msg.changed_at = ""
        entries = [(msg, "ch", "ts")]
        result = format_standard_status_changed_aggregated("", entries, 1)
        assert "X" in result
        # 名称部分不出现"（"（无名称时不追加括号内容）
        assert "（" not in result
        # 无 changed_at，不追加时间分隔符
        assert "，" not in result

    def test_expired_in_overflow_range(self):
        entries = [_make_entry(i, new_status="废止" if i >= 10 else "现行") for i in range(12)]
        result = format_standard_status_changed_aggregated("", entries, 12)
        assert "废止" in result


# ── do_test_send 全覆盖 ──

def _make_mgr(channels=None, cfg_data=None, creds=None, cred_helper_none=False):
    """构建模拟 NotificationManager，含 _channels、_cfg 与 _cred_helper。

    creds: dict[channel -> dict[str,str]]，模拟 user_credentials 表返回的凭证；
    cred_helper_none: True 时 _cred_helper 为 None（模拟 CredentialHelper 初始化失败）。
    """
    mgr = MagicMock()
    mgr._channels = channels or {}
    mgr._cfg = ConfigStub(cfg_data or {})
    mgr._user_id = 1
    if cred_helper_none:
        mgr._cred_helper = None
    else:
        helper = MagicMock()
        helper.get_channel.side_effect = lambda uid, ch: (creds or {}).get(ch)
        mgr._cred_helper = helper
    return mgr


class TestDoTestSendChannelExists:
    """渠道已在 _channels 中存在时的路径。"""

    def test_channel_exists_send_ok(self):
        ch = ChannelStub("telegram", should_succeed=True)
        mgr = _make_mgr(channels={"telegram": ch})
        result = do_test_send(mgr, "telegram", "hello")
        assert result == {"ok": True, "error": ""}
        assert len(ch.sent) == 1

    def test_channel_exists_send_fails(self):
        ch = ChannelStub("telegram", should_succeed=False)
        mgr = _make_mgr(channels={"telegram": ch})
        result = do_test_send(mgr, "telegram", "hello")
        assert result == {"ok": False, "error": "发送失败"}

    def test_channel_exists_send_raises(self):
        ch = MagicMock()
        ch.send.side_effect = RuntimeError("boom")
        mgr = _make_mgr(channels={"telegram": ch})
        result = do_test_send(mgr, "telegram", "hello")
        assert result == {"ok": False, "error": "boom"}


class TestDoTestSendUnknownChannel:
    """未知渠道路径。"""

    def test_unknown_channel(self):
        mgr = _make_mgr()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES", {}
        ):
            result = do_test_send(mgr, "no_such", "hello")
        assert result["ok"] is False
        assert "未知渠道" in result["error"]


class TestDoTestSendTelegram:
    """Telegram 渠道初始化路径（F-03：凭证源统一为 DB）。"""

    def test_missing_token(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"telegram": mock_cls},
        ):
            result = do_test_send(mgr, "telegram", "hello")
        assert result == {"ok": False, "error": "缺少 bot_token"}

    def test_missing_chat_id(self):
        mgr = _make_mgr(creds={"telegram": {"bot_token": "tok"}})
        mock_cls = MagicMock()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"telegram": mock_cls},
        ):
            result = do_test_send(mgr, "telegram", "hello")
        assert result == {"ok": False, "error": "缺少 chat_id"}

    def test_success_with_override(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"telegram": mock_cls},
        ):
            result = do_test_send(
                mgr, "telegram", "hello",
                params={"bot_token": "t", "chat_id": "c"},
            )
        assert result == {"ok": True, "error": ""}
        mock_cls.assert_called_once_with("t", "c")

    def test_success_with_db_fallback(self):
        """F-03：凭证从 DB（user_credentials）读取，config.json 旧值不再使用。"""
        mgr = _make_mgr(
            # config 中存在旧凭证，但 F-03 后不应被读取
            cfg_data={
                "notification.channels.telegram.bot_token": "cfg_old_tok",
                "notification.channels.telegram.chat_id": "cfg_old_cid",
            },
            creds={"telegram": {"bot_token": "db_tok", "chat_id": "db_cid"}},
        )
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"telegram": mock_cls},
        ):
            result = do_test_send(mgr, "telegram", "hello")
        assert result == {"ok": True, "error": ""}
        # 关键断言：使用 DB 凭证，而非 config 旧值
        mock_cls.assert_called_once_with("db_tok", "db_cid")

    def test_cred_helper_unavailable(self):
        """F-03：CredentialHelper 不可用（初始化失败）时报明确错误，不回退 config。"""
        mgr = _make_mgr(
            cred_helper_none=True,
            cfg_data={
                "notification.channels.telegram.bot_token": "cfg_tok",
                "notification.channels.telegram.chat_id": "cfg_cid",
            },
        )
        mock_cls = MagicMock()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"telegram": mock_cls},
        ):
            result = do_test_send(mgr, "telegram", "hello")
        assert result == {"ok": False, "error": "credential_helper_unavailable"}
        mock_cls.assert_not_called()


class TestDoTestSendDingtalk:
    """钉钉渠道初始化路径（F-03 O-1：凭证源统一为 DB）。"""

    def test_missing_url(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"dingtalk": mock_cls},
        ):
            result = do_test_send(mgr, "dingtalk", "hello")
        assert result == {"ok": False, "error": "缺少 webhook_url（钉钉群机器人必填）"}

    def test_success_with_override(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"dingtalk": mock_cls},
        ):
            result = do_test_send(
                mgr, "dingtalk", "hello",
                params={"webhook_url": "http://x", "secret": "s"},
            )
        assert result == {"ok": True, "error": ""}
        mock_cls.assert_called_once_with("http://x", "s")

    def test_success_with_db_fallback(self):
        """F-03 O-1：钉钉凭证从 DB 读取，config 旧值不再使用。"""
        mgr = _make_mgr(
            cfg_data={
                "notification.channels.dingtalk.webhook_url": "http://cfg_old",
            },
            creds={"dingtalk": {"webhook_url": "http://db_new", "secret": "db_secret"}},
        )
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"dingtalk": mock_cls},
        ):
            result = do_test_send(mgr, "dingtalk", "hello")
        assert result == {"ok": True, "error": ""}
        mock_cls.assert_called_once_with("http://db_new", "db_secret")


class TestDoTestSendFeishu:
    """飞书渠道初始化路径。"""

    def test_missing_url(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"feishu": mock_cls},
        ):
            result = do_test_send(mgr, "feishu", "hello")
        assert result == {"ok": False, "error": "缺少 webhook_url（飞书机器人必填）"}

    def test_success(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"feishu": mock_cls},
        ):
            result = do_test_send(
                mgr, "feishu", "hello",
                params={"webhook_url": "http://fs"},
            )
        assert result == {"ok": True, "error": ""}


class TestDoTestSendWechat:
    """企业微信渠道初始化路径 — 应用消息 vs 群机器人。"""

    def test_app_message_mode(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"wechat": mock_cls},
        ):
            result = do_test_send(
                mgr, "wechat", "hello",
                params={"corpid": "c1", "agentid": "a1", "corpsecret": "s1"},
            )
        assert result == {"ok": True, "error": ""}
        mock_cls.assert_called_once_with("c1", "a1", "s1")

    def test_webhook_mode(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"wechat": mock_cls},
        ):
            result = do_test_send(
                mgr, "wechat", "hello",
                params={"webhook_url": "http://wx"},
            )
        assert result == {"ok": True, "error": ""}
        mock_cls.assert_called_once_with("http://wx")

    def test_missing_both_modes(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"wechat": mock_cls},
        ):
            result = do_test_send(mgr, "wechat", "hello")
        assert result["ok"] is False
        assert "缺少" in result["error"]


class TestDoTestSendGeneric:
    """未知渠道类型走通用 webhook 路径。"""

    def test_generic_missing_url(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"custom": mock_cls},
        ):
            result = do_test_send(mgr, "custom", "hello")
        assert result["ok"] is False
        assert "缺少" in result["error"]

    def test_generic_success(self):
        mgr = _make_mgr()
        mock_cls = MagicMock()
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        mock_cls.return_value = mock_ch
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"custom": mock_cls},
        ):
            result = do_test_send(
                mgr, "custom", "hello",
                params={"webhook_url": "http://g"},
            )
        assert result == {"ok": True, "error": ""}


class TestDoTestSendInitError:
    """初始化异常路径。"""

    def test_init_raises(self):
        mgr = _make_mgr()
        mock_cls = MagicMock(side_effect=ValueError("init fail"))
        with patch(
            "pilotstd.core.notification.manager._CHANNEL_CLASSES",
            {"telegram": mock_cls},
        ):
            result = do_test_send(
                mgr, "telegram", "hello",
                params={"bot_token": "t", "chat_id": "c"},
            )
        assert result["ok"] is False
        assert "渠道初始化失败" in result["error"]
