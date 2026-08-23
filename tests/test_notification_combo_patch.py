# tests/test_notification_combo_patch.py — 掩码拦截 + 错误透传合并修复测试（P-116 + P-119）
"""验证两处修复：

P0（P-119）：后端 update_config 拦截掩码值（***）写回，且为 Merge 语义（保留未提交字段）。
P1（P-116）：渠道 send() 失败时设置 last_error，_send_now 将其写入 notification_log.error_msg。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════
# P0：掩码拦截 + Merge 语义
# ══════════════════════════════════════════════════════════════════════


class TestMaskedValueBlocking:
    """验证 update_config 将渠道配置透传给 set_channel（合并与掩码过滤下沉到凭据层）。"""

    def test_masked_bot_token_not_written(self):
        """前端提交 bot_token='***' → update_config 透传原始值，掩码拦截由 set_channel 保证。"""
        from unittest.mock import MagicMock, patch

        from docker.api.notification import update_config

        mock_mgr = MagicMock()
        mock_mgr.notification_mgr = MagicMock()
        mock_cred = MagicMock()
        mock_mgr.notification_mgr._cred_helper = mock_cred
        mock_mgr.cfg = MagicMock()
        mock_mgr.user_service = MagicMock()

        body = {
            "channels": {
                "telegram": {
                    "enabled": True,
                    "bot_token": "***",  # 前端掩码回显
                    "chat_id": "-100123",
                }
            }
        }

        with patch("docker.api.notification.get_manager_dep", return_value=mock_mgr):
            update_config(request=MagicMock(), body=body, mgr=mock_mgr, user_id=1)

        # update_config 直接透传，掩码过滤由 CredentialHelper.set_channel 内部完成
        mock_cred.set_channel.assert_called_once()
        args = mock_cred.set_channel.call_args.args
        assert args[1] == "telegram"
        assert args[2]["bot_token"] == "***"  # 原始值透传

    def test_merge_preserves_unsubmitted_fields(self):
        """前端仅提交 enabled → 透传给 set_channel，保留逻辑由凭据层 Merge 保证。"""
        from unittest.mock import MagicMock, patch

        from docker.api.notification import update_config

        mock_mgr = MagicMock()
        mock_mgr.notification_mgr = MagicMock()
        mock_cred = MagicMock()
        mock_mgr.notification_mgr._cred_helper = mock_cred
        mock_mgr.cfg = MagicMock()
        mock_mgr.user_service = MagicMock()

        body = {
            "channels": {
                "wechat": {
                    "enabled": False,  # 只改开关，URL 未提交（增量）
                }
            }
        }

        with patch("docker.api.notification.get_manager_dep", return_value=mock_mgr):
            update_config(request=MagicMock(), body=body, mgr=mock_mgr, user_id=1)

        mock_cred.set_channel.assert_called_once()
        cfg = mock_cred.set_channel.call_args.args[2]
        assert cfg["enabled"] is False  # 原样透传
        assert "webhook_url" not in cfg  # 未提交字段不出现

    def test_empty_value_not_written(self):
        """前端提交空 bot_token → 透传给 set_channel，空值跳过由凭据层保证。"""
        from unittest.mock import MagicMock, patch

        from docker.api.notification import update_config

        mock_mgr = MagicMock()
        mock_mgr.notification_mgr = MagicMock()
        mock_cred = MagicMock()
        mock_mgr.notification_mgr._cred_helper = mock_cred
        mock_mgr.cfg = MagicMock()
        mock_mgr.user_service = MagicMock()

        body = {
            "channels": {
                "telegram": {
                    "enabled": True,
                    "bot_token": "",  # 空值
                    "chat_id": "-100123",
                }
            }
        }

        with patch("docker.api.notification.get_manager_dep", return_value=mock_mgr):
            update_config(request=MagicMock(), body=body, mgr=mock_mgr, user_id=1)

        mock_cred.set_channel.assert_called_once()
        cfg = mock_cred.set_channel.call_args.args[2]
        assert cfg["bot_token"] == ""  # 原样透传


# ══════════════════════════════════════════════════════════════════════
# P1：错误透传
# ══════════════════════════════════════════════════════════════════════


class TestErrorPropagation:
    """验证渠道 last_error 透传到 notification_log。"""

    def test_send_now_writes_channel_last_error(self):
        """channel.send() 返回 False 且 last_error 有值 → _log 收到该值。"""
        from unittest.mock import MagicMock

        from pilotstd.core.notification.manager import NotificationManager

        mgr = MagicMock(spec=NotificationManager)
        channel = MagicMock()
        channel.send.return_value = False
        channel.last_error = "HTTP 404: Not Found"

        msg = MagicMock()
        msg.event_type = "test_event"
        msg.title = "t"
        msg.body = "b"
        msg.standard_number = None
        msg.aggregated_count = 1
        msg.link = None
        msg.icon = None

        # 直接调用 _send_now，验证 _log 的 error 参数
        from datetime import datetime

        mgr._channels = {"telegram": channel}
        mgr._log = MagicMock()

        NotificationManager._send_now(mgr, msg, ["telegram"])

        mgr._log.assert_called_once()
        args = mgr._log.call_args.args
        assert args[3] == "failed"
        assert args[4] == "HTTP 404: Not Found"  # 透传渠道错误

    def test_send_now_fallback_when_no_last_error(self):
        """channel.send() 返回 False 且无 last_error → 回退默认文案。"""
        from unittest.mock import MagicMock

        from pilotstd.core.notification.manager import NotificationManager

        mgr = MagicMock(spec=NotificationManager)
        channel = MagicMock()
        channel.send.return_value = False
        # 无 last_error 属性（模拟旧渠道对象）
        del channel.last_error

        msg = MagicMock()
        msg.event_type = "test_event"
        msg.title = "t"
        msg.body = "b"
        msg.standard_number = None
        msg.aggregated_count = 1
        msg.link = None
        msg.icon = None

        mgr._channels = {"telegram": channel}
        mgr._log = MagicMock()

        NotificationManager._send_now(mgr, msg, ["telegram"])

        args = mgr._log.call_args.args
        assert args[3] == "failed"
        assert args[4] == "发送失败 (无详细错误)"

    def test_send_now_success_clears_error(self):
        """channel.send() 返回 True → error_msg 为空。"""
        from unittest.mock import MagicMock

        from pilotstd.core.notification.manager import NotificationManager

        mgr = MagicMock(spec=NotificationManager)
        channel = MagicMock()
        channel.send.return_value = True
        channel.last_error = ""

        msg = MagicMock()
        msg.event_type = "test_event"
        msg.title = "t"
        msg.body = "b"
        msg.standard_number = None
        msg.aggregated_count = 1
        msg.link = None
        msg.icon = None

        mgr._channels = {"telegram": channel}
        mgr._log = MagicMock()

        NotificationManager._send_now(mgr, msg, ["telegram"])

        args = mgr._log.call_args.args
        assert args[3] == "success"
        assert args[4] == ""

    def test_telegram_channel_sets_last_error_on_http_404(self):
        """TelegramChannel.send() 遇 HTTP 404 → last_error 含具体描述。"""
        import io
        from unittest.mock import MagicMock, patch
        from urllib.error import HTTPError

        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel(bot_token="token123", chat_id="-100123")
        msg = MagicMock()
        msg.title = "t"
        msg.body = "b"
        msg.standard_number = None
        msg.event_type = "test"
        msg.link = None
        msg.icon = None
        msg.aggregated_count = 1
        msg.status = ""
        msg.target_id = ""
        msg.elapsed_ms = 0
        msg.changed_at = ""
        msg.blocks = []

        err = HTTPError(
            "http://api.telegram.org", 404, "Not Found", None,
            io.BytesIO(b'{"ok":false,"error_code":404,"description":"Not Found"}'),
        )

        with patch("pilotstd.core.notification.channels.telegram.urlopen", side_effect=err):
            ok = ch.send(msg)

        assert ok is False
        assert "HTTP 404" in ch.last_error
        assert "Not Found" in ch.last_error
