# tests/test_notification_core.py — 通知模块核心组件补充测试

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


class TestMakeLink(unittest.TestCase):
    def test_with_standard_number(self):
        from pilotstd.core.notification._message_builders import _make_link

        self.assertEqual(_make_link("GB/T 1.1-2020"), "/standards/GB/T 1.1-2020")

    def test_none_returns_none(self):
        from pilotstd.core.notification._message_builders import _make_link

        self.assertIsNone(_make_link(None))

    def test_empty_string_returns_none(self):
        from pilotstd.core.notification._message_builders import _make_link

        self.assertIsNone(_make_link(""))


class TestMessageBuilders(unittest.TestCase):
    def setUp(self):
        from pilotstd.core.notification._message_builders import MessageBuildersMixin

        self.mixin = MessageBuildersMixin()

    def test_archive_complete_with_dirs(self):
        msg = self.mixin._build_archive_complete_message({"count": 5, "directories": ["d1", "d2", "d3", "d4", "d5"]})
        self.assertEqual(msg.level, "info")
        # blocks[0] 为 TextBlock("已归档 5 个目录"), blocks[1] 为 ListBlock
        self.assertIn("5", msg.blocks[0].text)

    def test_archive_complete_zero(self):
        msg = self.mixin._build_archive_complete_message({"count": 0, "directories": []})
        self.assertIn("未归档", msg.blocks[0].text)

    def test_status_changed_expired(self):
        msg = self.mixin._build_standard_status_changed_message(
            {"standard_number": "GB/T 1.1", "old_status": "现行", "new_status": "废止", "is_expired": True}
        )
        self.assertEqual(msg.level, "error")

    def test_status_changed_normal(self):
        msg = self.mixin._build_standard_status_changed_message(
            {"standard_number": "GB/T 1.1", "old_status": "现行", "new_status": "即将实施", "is_expired": False}
        )
        self.assertEqual(msg.level, "info")

    def test_standard_expired(self):
        msg = self.mixin._build_standard_expired_message({"standard_number": "GB/T 1.1"})
        self.assertIsNotNone(msg)

    def test_standard_first_registered(self):
        msg = self.mixin._build_standard_first_registered_message({"standard_number": "GB/T 1.1"})
        self.assertIsNotNone(msg)

    def test_batch_download_complete(self):
        msg = self.mixin._build_batch_download_complete_message({"count": 3, "failed": 0})
        self.assertEqual(msg.level, "info")

    def test_batch_download_with_failures(self):
        msg = self.mixin._build_batch_download_complete_message({"count": 5, "failed": 2})
        # blocks[1] 为 KeyValueBlock(key="失败", value="2")
        self.assertEqual(msg.blocks[1].value, "2")

    def test_worker_error(self):
        msg = self.mixin._build_worker_error_message(
            {"standard_number": "TEST", "error": "Connection refused", "source_site": "test"}
        )
        self.assertEqual(msg.level, "error")

    def test_auto_query_complete(self):
        msg = self.mixin._build_auto_query_complete_message({"count": 10})
        self.assertEqual(msg.level, "info")

    def test_batch_query_summary(self):
        msg = self.mixin._build_batch_query_summary_message({"total": 100, "success": 95, "failed": 5})
        self.assertIsNotNone(msg)

    def test_validity_batch_report(self):
        msg = self.mixin._build_validity_batch_report_message({"total": 50, "changed": 3, "expired": 1, "details": []})
        self.assertIsNotNone(msg)

    def test_validity_round_summary(self):
        msg = self.mixin._build_validity_round_summary_message(
            {"total_checked": 100, "changed": 5, "expired_new": 2, "elapsed_ms": 5000}
        )
        self.assertIsNotNone(msg)

    def test_fallback_message(self):
        msg = self.mixin._build_fallback_message("custom_event", {"key": "val"})
        self.assertEqual(msg.title, "custom_event")

    def test_announcement_fetch_complete(self):
        msg = self.mixin._build_announcement_fetch_complete_message(
            {"source_site": "test", "count": 10, "new_count": 3}
        )
        self.assertIsNotNone(msg)

    def test_check_batch_complete(self):
        msg = self.mixin._build_check_batch_complete_message({"total": 20, "success": 18, "failed": 2})
        self.assertIsNotNone(msg)

    def test_image_update_available(self):
        msg = self.mixin._build_image_update_available_message({"version": "2.0.0", "url": "https://..."})
        self.assertIsNotNone(msg)

    def test_trust_ip_update(self):
        msg = self.mixin._build_trust_ip_update_message({"ip": "192.168.1.1"})
        self.assertIsNotNone(msg)


class TestNotificationPolicyHelper(unittest.TestCase):
    def test_get_channels_for_event_from_db(self):
        from pilotstd.core.notification._policy import NotificationPolicyHelper

        db = MagicMock()
        db.fetchall.return_value = [
            {"channel": "wechat", "events": '["test_event", "other"]'},
            {"channel": "telegram", "events": '["other"]'},
        ]
        helper = NotificationPolicyHelper(db, MagicMock())
        channels = helper.get_channels_for_event(1, "test_event")
        self.assertEqual(channels, ["wechat"])

    def test_get_channels_fallback_list(self):
        from pilotstd.core.notification._policy import NotificationPolicyHelper

        db = MagicMock()
        db.fetchall.return_value = []
        cfg = MagicMock()
        cfg.get.return_value = ["wechat", "telegram"]
        helper = NotificationPolicyHelper(db, cfg)
        channels = helper.get_channels_for_event(1, "test_event")
        self.assertEqual(channels, ["wechat", "telegram"])

    def test_get_channels_fallback_string(self):
        from pilotstd.core.notification._policy import NotificationPolicyHelper

        db = MagicMock()
        db.fetchall.return_value = []
        cfg = MagicMock()
        cfg.get.return_value = "wechat, telegram"
        helper = NotificationPolicyHelper(db, cfg)
        channels = helper.get_channels_for_event(1, "test_event")
        self.assertEqual(channels, ["wechat", "telegram"])

    def test_get_channels_no_match(self):
        from pilotstd.core.notification._policy import NotificationPolicyHelper

        db = MagicMock()
        db.fetchall.return_value = []
        cfg = MagicMock()
        cfg.get.return_value = None
        helper = NotificationPolicyHelper(db, cfg)
        channels = helper.get_channels_for_event(1, "nonexistent")
        self.assertEqual(channels, [])

    def test_get_policies(self):
        from pilotstd.core.notification._policy import NotificationPolicyHelper

        db = MagicMock()
        db.fetchall.return_value = [
            {"id": 1, "channel": "wechat", "enabled": 1, "events": '["a"]', "updated_at": "2024-01-01"}
        ]
        helper = NotificationPolicyHelper(db, MagicMock())
        policies = helper.get_policies(1)
        self.assertEqual(len(policies), 1)
        self.assertTrue(policies[0]["enabled"])

    def test_save_policy_insert(self):
        from pilotstd.core.notification._policy import NotificationPolicyHelper

        db = MagicMock()
        db.fetchone.return_value = None
        helper = NotificationPolicyHelper(db, MagicMock())
        helper.save_policy(1, "wechat", True, ["event1"])
        db.execute.assert_called()

    def test_save_policy_update_enabled(self):
        from pilotstd.core.notification._policy import NotificationPolicyHelper

        db = MagicMock()
        db.fetchone.return_value = {"id": 1}
        helper = NotificationPolicyHelper(db, MagicMock())
        helper.save_policy(1, "wechat", False, None)
        db.execute.assert_called()


class TestCredentialHelper(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_channel(self):
        from pilotstd.core.notification._credentials import CredentialHelper

        db = MagicMock()
        helper = CredentialHelper(db, self.tmpdir)
        helper.set_channel(1, "wechat", {"webhook_url": "https://e.com"})
        db.execute.assert_called()

    def test_delete_channel(self):
        from pilotstd.core.notification._credentials import CredentialHelper

        db = MagicMock()
        helper = CredentialHelper(db, self.tmpdir)
        helper.delete_channel(1, "telegram")
        db.execute.assert_called()

    def test_get_channel_none(self):
        from pilotstd.core.notification._credentials import CredentialHelper

        db = MagicMock()
        db.fetchone.return_value = None
        helper = CredentialHelper(db, self.tmpdir)
        result = helper.get_channel(1, "wechat")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
