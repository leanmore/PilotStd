# tests/test_notification_channels.py — 通知渠道初始化与接口测试

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


class TestTelegramChannel(unittest.TestCase):
    def test_init(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        ch = TelegramChannel("test_token", "12345")
        self.assertTrue(hasattr(ch, 'send'))

    def test_validate_config(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel
        self.assertTrue(TelegramChannel.validate_config({"bot_token": "x", "chat_id": "1"}))


class TestWechatChannel(unittest.TestCase):
    def test_init(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel
        ch = WechatChannel("https://example.com/webhook")
        self.assertTrue(hasattr(ch, 'send'))


class TestFeishuChannel(unittest.TestCase):
    def test_init(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel
        ch = FeishuChannel("https://open.feishu.cn/test")
        self.assertTrue(hasattr(ch, 'send'))


class TestDingTalkChannel(unittest.TestCase):
    def test_init(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("https://oapi.dingtalk.com/test")
        self.assertTrue(hasattr(ch, 'send'))

    def test_init_with_secret(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel
        ch = DingTalkChannel("https://oapi.dingtalk.com/test", secret="sec")
        self.assertTrue(hasattr(ch, 'send'))


class TestNotifDesktopFormatter(unittest.TestCase):
    def test_format_for_desktop(self):
        from pilotstd.core.notification.desktop_formatter import format_for_desktop
        title, body = format_for_desktop("Test Title", "Test Body")
        self.assertIsInstance(title, str)


class TestNotificationEvents(unittest.TestCase):
    def test_event_defs(self):
        from pilotstd.core.notification.events import ALL_EVENT_KEYS
        self.assertGreater(len(ALL_EVENT_KEYS), 0)


class TestNotificationMessage(unittest.TestCase):
    def test_message_fields(self):
        from pilotstd.core.notification.channel import NotificationMessage
        msg = NotificationMessage(title="T", body="B", level="warning", event_type="e", standard_number="S001")
        self.assertEqual(msg.title, "T")
        self.assertEqual(msg.standard_number, "S001")

    def test_repr(self):
        from pilotstd.core.notification.channel import NotificationMessage
        msg = NotificationMessage(title="T", body="B", level="info", event_type="e")
        self.assertIn("T", repr(msg))


if __name__ == "__main__":
    unittest.main()
