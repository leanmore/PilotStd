# tests/test_p0_modules.py — P0 补测：facade + channels

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _mock_urlopen_success(response_bytes: bytes = b'{"ok":true}'):
    """返回一个模拟成功 HTTP 响应的 urlopen mock。"""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = response_bytes
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_resp)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_cm)


def _make_manager_core():
    """快速组装一个 manager_core mock。"""
    core = MagicMock()
    core.cfg = MagicMock()
    core.cfg.get.return_value = None
    core.db = MagicMock()
    core.parser = MagicMock()
    core.scanner = MagicMock()
    core.query_engine = MagicMock()
    core.cache = MagicMock()
    core.quota_tracker = MagicMock()
    core.adapter_manager = MagicMock()
    core.file_index = MagicMock()
    core.download_engine = MagicMock()
    core.session_mgr = MagicMock()
    core.task_queue = MagicMock()
    core.router = MagicMock()
    core._file_watcher = None
    core.classifier = MagicMock()
    core.organizer_svc = MagicMock()
    core.announce_svc = MagicMock()
    core.pending_svc = MagicMock()
    core.scheduled_svc = MagicMock()
    core.validity_checker = MagicMock()
    core.notification_mgr = MagicMock()
    core.pipeline_store = MagicMock()
    core.parsed_results = []
    core.queried_items = []
    core.query_results = []
    core.download_list = []
    core.expire_list = []
    core.pending_list = []
    core.download_tasks = []
    core.last_skipped_dirs = []
    return core


# ═══════════════════════════════════════════════════════
# 通知渠道测试
# ═══════════════════════════════════════════════════════


class TestTelegramChannelFull(unittest.TestCase):
    def test_validate_config_ok(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel

        self.assertTrue(TelegramChannel.validate_config({"bot_token": "x", "chat_id": "1"}))
        self.assertFalse(TelegramChannel.validate_config({"bot_token": "x"}))

    def test_log_dedup(self):
        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel("tok", "chat")
        ch._log_dedup("unique error")
        self.assertEqual(ch._last_error_key, "unique error")

    def test_log_dedup_suppressed(self):

        from pilotstd.core.notification.channels.telegram import TelegramChannel

        ch = TelegramChannel("tok", "chat")
        ch._log_dedup("repeat")
        t1 = ch._last_error_time
        ch._log_dedup("repeat")  # should be suppressed - time diff < 120s
        self.assertEqual(ch._last_error_time, t1)

    @patch("pilotstd.core.notification.channels.telegram.urlopen")
    def test_send_ok(self, mock_urlopen):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.telegram import TelegramChannel

        mock_urlopen.side_effect = _mock_urlopen_success(b'{"ok":true}')
        ch = TelegramChannel("tok123", "chat456")
        msg = NotificationMessage(title="T", body="B", level="info", event_type="e")
        self.assertTrue(ch.send(msg))

    @patch("pilotstd.core.notification.channels.telegram.urlopen")
    def test_send_api_error(self, mock_urlopen):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.telegram import TelegramChannel

        mock_urlopen.side_effect = _mock_urlopen_success(b'{"ok":false,"description":"bad"}')
        ch = TelegramChannel("tok", "chat")
        msg = NotificationMessage(title="T", body="B", level="info", event_type="e")
        self.assertFalse(ch.send(msg))


class TestWechatChannelFull(unittest.TestCase):
    def test_validate_config(self):
        from pilotstd.core.notification.channels.wechat import WechatChannel

        self.assertTrue(WechatChannel.validate_config({"webhook_url": "https://e.com"}))
        self.assertFalse(WechatChannel.validate_config({}))

    @patch("pilotstd.core.notification.channels.wechat.urlopen")
    def test_send_success(self, mock_urlopen):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.wechat import WechatChannel

        mock_urlopen.side_effect = _mock_urlopen_success()
        ch = WechatChannel("https://e.com/webhook")
        msg = NotificationMessage(title="T", body="B", level="info", event_type="e", standard_number="S001")
        self.assertTrue(ch.send(msg))


class TestFeishuChannelFull(unittest.TestCase):
    def test_validate_config(self):
        from pilotstd.core.notification.channels.feishu import FeishuChannel

        self.assertTrue(FeishuChannel.validate_config({"webhook_url": "https://e.com"}))
        self.assertFalse(FeishuChannel.validate_config({"webhook_url": ""}))

    @patch("pilotstd.core.notification.channels.feishu.urlopen")
    def test_send_success(self, mock_urlopen):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.feishu import FeishuChannel

        mock_urlopen.side_effect = _mock_urlopen_success(b'{"code":0}')
        ch = FeishuChannel("https://open.feishu.cn/test")
        msg = NotificationMessage(title="T", body="B", level="warning", event_type="e")
        self.assertTrue(ch.send(msg))

    @patch("pilotstd.core.notification.channels.feishu.urlopen")
    def test_send_api_error(self, mock_urlopen):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.feishu import FeishuChannel

        mock_urlopen.side_effect = _mock_urlopen_success(b'{"code":1,"msg":"error"}')
        ch = FeishuChannel("https://e.com")
        msg = NotificationMessage(title="T", body="B", level="info", event_type="e")
        self.assertFalse(ch.send(msg))


class TestDingTalkChannelFull(unittest.TestCase):
    def test_validate_config(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        self.assertTrue(DingTalkChannel.validate_config({"webhook_url": "https://e.com"}))
        self.assertFalse(DingTalkChannel.validate_config({"webhook_url": ""}))

    def test_sign_empty(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        ch = DingTalkChannel("https://e.com", secret="")
        self.assertEqual(ch._sign(), "")

    def test_sign_with_secret(self):
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        ch = DingTalkChannel("https://e.com", secret="mysecret")
        sig = ch._sign()
        self.assertIn("timestamp", sig)
        self.assertIn("sign", sig)

    @patch("pilotstd.core.notification.channels.dingtalk.urlopen")
    def test_send_success(self, mock_urlopen):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        mock_urlopen.side_effect = _mock_urlopen_success(b'{"errcode":0}')
        ch = DingTalkChannel("https://oapi.dingtalk.com/test")
        msg = NotificationMessage(title="T", body="B", level="info", event_type="e")
        self.assertTrue(ch.send(msg))

    @patch("pilotstd.core.notification.channels.dingtalk.urlopen")
    def test_send_with_secret(self, mock_urlopen):
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.channels.dingtalk import DingTalkChannel

        mock_urlopen.side_effect = _mock_urlopen_success(b'{"errcode":0}')
        ch = DingTalkChannel("https://e.com", secret="SEC")
        msg = NotificationMessage(title="T", body="B", level="info", event_type="e")
        self.assertTrue(ch.send(msg))


# ═══════════════════════════════════════════════════════
# Manager Facade 测试
# ═══════════════════════════════════════════════════════


class TestQueryHandler(unittest.TestCase):
    def setUp(self):
        self.core = _make_manager_core()

    def test_init(self):
        from pilotstd.manager.facade._query import QueryHandler

        h = QueryHandler(self.core)
        self.assertEqual(h._core, self.core)

    def test_set_pause_event(self):
        from pilotstd.manager.facade._query import QueryHandler

        h = QueryHandler(self.core)
        h.set_pause_event("event_obj")
        self.core.query_engine.set_pause_event.assert_called_with("event_obj")

    def test_query_announcement_no_api_key(self):
        from pilotstd.manager.facade._query import QueryHandler

        self.core.cfg.get.return_value = ""
        h = QueryHandler(self.core)
        result = h._query_announcement_match("GB/T 1.1")
        self.assertIsNone(result)

    def test_build_result_from_cache(self):
        from pilotstd.manager.facade._query import QueryHandler

        cache_data = {"standard_number": "GB/T 1.1", "standard_name": "Test", "status": "现行"}
        result = QueryHandler._build_result_from_cache("GB/T 1.1", cache_data)
        self.assertEqual(result.standard_number, "GB/T 1.1")

    def test_cat_label_mapping(self):
        from pilotstd.manager.facade._query import QueryHandler

        h = QueryHandler(self.core)
        self.assertEqual(h._CAT_LABEL["gb"], "国标")
        self.assertEqual(h._CAT_LABEL["foreign"], "国外标准")


class TestDownloadHandler(unittest.TestCase):
    def setUp(self):
        self.core = _make_manager_core()

    def test_init(self):
        from pilotstd.manager.facade._download import DownloadHandler

        h = DownloadHandler(self.core)
        self.assertEqual(h._core, self.core)

    def test_set_organize_handler(self):
        from pilotstd.manager.facade._download import DownloadHandler

        h = DownloadHandler(self.core)
        mock_org = MagicMock()
        h._set_organize_handler(mock_org)
        self.assertEqual(h._organize_handler, mock_org)

    def test_handle_expired_if_needed_empty(self):
        from pilotstd.manager.facade._download import DownloadHandler

        h = DownloadHandler(self.core)
        h._handle_expired_if_needed()  # empty expire_list → no action

    def test_handle_expired_if_needed_with_items(self):
        from pilotstd.manager.facade._download import DownloadHandler

        mock_org = MagicMock()
        h = DownloadHandler(self.core)
        h._set_organize_handler(mock_org)
        self.core.expire_list = ["item1"]
        h._handle_expired_if_needed()
        mock_org.handle_expired.assert_called_once()


class TestAutoPipeline(unittest.TestCase):
    def setUp(self):
        self.core = _make_manager_core()

    def test_init(self):
        from pilotstd.manager.facade._auto import AutoPipeline

        scan = MagicMock()
        query = MagicMock()
        download = MagicMock()
        organize = MagicMock()
        ap = AutoPipeline(self.core, scan, query, download, organize)
        self.assertEqual(ap._core, self.core)

    def test_auto_run(self):
        from pilotstd.manager.facade._auto import AutoPipeline

        scan = MagicMock()
        scan.scan_directory.return_value = [MagicMock(), MagicMock()]
        query = MagicMock()
        query.query.return_value = (MagicMock(), MagicMock())
        query.query.return_value[1].found = 1
        download = MagicMock()
        download.download.return_value = ([], MagicMock())
        download.download.return_value[1].success = 0
        organize = MagicMock()
        ap = AutoPipeline(self.core, scan, query, download, organize)
        report = ap.auto_run("/test/path")
        self.assertEqual(report["scan"], 2)
        self.assertEqual(report["query_found"], 1)


if __name__ == "__main__":
    unittest.main()
