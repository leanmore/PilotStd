# tests/test_notification_manager_extended.py — NotificationManager 深度补测

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


class TestNotificationManagerExtended(unittest.TestCase):
    def setUp(self):
        self.mock_cfg = MagicMock()
        self.mock_cfg.get.return_value = False
        self.mock_cfg._filepath = os.path.join(os.path.dirname(__file__), "test_cfg.json")
        self.mock_db = MagicMock()

    def test_init_disabled_no_channels(self):
        from pilotstd.core.notification import NotificationManager

        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        self.assertFalse(nmgr._enabled)

    @patch("pilotstd.core.notification.manager.CredentialHelper")
    def test_init_with_ws_broadcast(self, _cred):
        from pilotstd.core.notification import NotificationManager

        _cred.return_value = MagicMock()
        _cred.return_value.get_all.return_value = {}
        ws = MagicMock()
        self.mock_cfg.get.side_effect = lambda k, d=None: {"notification.enabled": True}.get(k, d)
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1, ws_broadcast=ws)
        self.assertEqual(nmgr._ws_broadcast, ws)

    @patch("pilotstd.core.notification.manager.CredentialHelper")
    @patch("pilotstd.core.notification.manager.WechatChannel")
    def test_send_event_with_aggregator_disabled(self, _wc, _cred):
        from pilotstd.core.notification import NotificationManager

        _cred.return_value = MagicMock()
        _cred.return_value.get_all.return_value = {}
        mock_ch = MagicMock()
        mock_ch.send.return_value = True
        _wc.return_value = mock_ch
        self.mock_cfg.get.side_effect = lambda k, d=None: {
            "notification.enabled": True,
            "notification.aggregate_enabled": False,
            "notification.channels.wechat.enabled": True,
            "notification.channels.wechat.webhook_url": "https://e.com",
            "notification.rules.test_event": ["wechat"],
        }.get(k, d)
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        result = nmgr.send_event("test_event", {"key": "val"})
        self.assertIsNone(result)

    def test_build_message_all_events(self):
        """验证所有已知事件的消息构建不抛出异常。"""
        from pilotstd.core.notification import NotificationManager

        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        events = [
            ("archive_complete", {"count": 1, "directories": ["d1"]}),
            (
                "standard_status_changed",
                {"standard_number": "T", "old_status": "A", "new_status": "B", "is_expired": False},
            ),
            ("standard_first_registered", {"standard_number": "T"}),
            ("scan_complete", {"count": 10, "failed": 2}),
            ("announcement_fetch_complete", {"source_site": "s", "count": 5, "new_count": 2}),
            ("announcement_check_complete", {"source_site": "s", "total_fetched": 10, "new_standards": 3}),
            ("auto_backup", {"path": "/b", "size_mb": 10}),
            ("auto_scan_failed", {"error": "e"}),
            ("validity_batch_report", {"total": 50, "changed": 3, "expired": 1, "details": []}),
            ("validity_round_summary", {"total_checked": 100, "changed": 5, "expired_new": 2, "elapsed_ms": 5000}),
            ("validity_standard_failed", {"standard_number": "T", "error": "e"}),
            ("validity_system_failed", {"error": "e"}),
            ("batch_download_complete", {"count": 3, "failed": 0}),
            ("normalize_complete", {"total": 10, "success": 9, "failed": 1}),
            ("batch_query_summary", {"total": 100, "success": 95, "failed": 5}),
            ("worker_error", {"standard_number": "T", "error": "e", "source_site": "s"}),
            ("image_update_available", {"version": "2.0", "url": "https://..."}),
            ("trust_ip_update", {"ip": "192.168.1.1"}),
        ]
        for event_type, data in events:
            msg = nmgr._build_message(event_type, data)
            self.assertIsNotNone(msg, f"Failed to build message for {event_type}")
            self.assertIsInstance(msg.title, str)


if __name__ == "__main__":
    unittest.main()
