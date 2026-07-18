# tests/test_channels_announcement.py — 通知渠道 + 公告解析测试

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


class TestTelegramChannel(unittest.TestCase):
    def test_init_strips(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel(" mytoken ", " 12345 ")
        self.assertEqual(ch._token, "mytoken")

    def test_send_no_token(self):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel("", "12345")
        self.assertFalse(ch.send(NotificationMessage(title="T", body="B", level="info", event_type="e")))

    def test_has_send_method(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel("t", "c")
        self.assertTrue(callable(ch.send))


class TestWechatChannel(unittest.TestCase):
    def test_send_empty_url(self):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.wechat import WechatChannel

        self.assertFalse(WechatChannel("").send(NotificationMessage(title="T", body="B", level="info", event_type="e")))

    def test_has_send_method(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel

        self.assertTrue(callable(WechatChannel("https://e.com").send))


class TestFeishuChannel(unittest.TestCase):
    def test_has_send_method(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel

        self.assertTrue(callable(FeishuChannel("https://e.com").send))


class TestDingTalkChannel(unittest.TestCase):
    def test_init_with_secret(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        ch = DingTalkChannel("https://oapi.dingtalk.com/test", secret="SEC123")
        self.assertTrue(callable(ch.send))

    def test_init_without_secret(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        ch = DingTalkChannel("https://oapi.dingtalk.com/test")
        self.assertTrue(callable(ch.send))


class TestAnnouncementParser(unittest.TestCase):
    def test_std_code_pattern(self):
        from pilotstd.announcement.parser import STD_CODE_PATTERN

        self.assertTrue(STD_CODE_PATTERN.match("GB/T 1.1-2020"))
        self.assertTrue(STD_CODE_PATTERN.match("ISO 9001-2015"))

    def test_parse_attachment_text_empty(self):
        from pilotstd.announcement.parser import parse_attachment_text

        result = parse_attachment_text(b"", "test.wps")
        self.assertEqual(result, "")

    def test_parse_wps_text_empty(self):
        from pilotstd.announcement.parser import parse_wps_text

        result = parse_wps_text(b"")
        self.assertEqual(result, "")


class TestAnnouncementBase(unittest.TestCase):
    def test_finalize_items(self):
        from pilotstd.announcement.base import BaseAnnounceCrawler

        items = [{"std_code": "GB/T 1.1"}]
        result = BaseAnnounceCrawler._finalize_items(items, "http://example.com/att.wps")
        self.assertEqual(result[0]["attachment_url"], "http://example.com/att.wps")


if __name__ == "__main__":
    unittest.main()
