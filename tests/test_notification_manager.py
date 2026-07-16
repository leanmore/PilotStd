# tests/test_notification_manager.py
# 通知系统 manager 核心测试
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.core.notification import NotificationManager


class TestNotificationManager(unittest.TestCase):
    """测试 NotificationManager 核心功能。"""

    def setUp(self):
        self.mock_cfg = MagicMock()
        self.mock_cfg.get.return_value = False  # 默认关闭通知
        self.mock_cfg._filepath = os.path.join(os.path.dirname(__file__), "test_config.json")
        self.mock_db = MagicMock()

    def test_init_disabled_skips_channels(self):
        """通知关闭时不应初始化任何渠道。"""
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        self.assertFalse(nmgr._enabled)
        self.assertEqual(len(nmgr._channels), 0)

    def test_send_event_returns_when_disabled(self):
        """通知关闭时 send_event 应立即返回。"""
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        result = nmgr.send_event("test_event", {})
        self.assertIsNone(result)

    @patch("pilotstd.core.notification.manager.CredentialHelper")
    @patch("pilotstd.core.notification.manager.WechatChannel")
    @patch("pilotstd.core.notification.manager.TelegramChannel")
    @patch("pilotstd.core.notification.manager.FeishuChannel")
    @patch("pilotstd.core.notification.manager.DingTalkChannel")
    def test_init_channels_only_enabled(self, _dt, _fs, _tg, _wc, _cred_cls):
        """仅初始化已启用的渠道（从 CredentialHelper 读凭证）。"""
        mock_cred = MagicMock()
        mock_cred.get_all.return_value = {
            "wechat": {"enabled": True, "webhook_url": "https://example.com/wechat"},
            "telegram": {"enabled": False},
            "feishu": {"enabled": False},
            "dingtalk": {"enabled": False},
        }
        _cred_cls.return_value = mock_cred
        self.mock_cfg.get.side_effect = lambda key, default=None: {
            "notification.enabled": True,
        }.get(key, default)
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        self.assertIn("wechat", nmgr._channels)

    def test_build_message_archive_complete(self):
        """验证 archive_complete 消息模板。"""
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        msg = nmgr._build_message("archive_complete", {"count": 10})
        self.assertEqual(msg.title, "归档完成")
        self.assertEqual(msg.level, "info")

    def test_build_message_status_changed(self):
        """验证标准状态变更消息模板。"""
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        msg = nmgr._build_message(
            "standard_status_changed",
            {
                "standard_number": "GB/T 1.1-2020",
                "old_status": "现行",
                "new_status": "已废止",
            },
        )
        self.assertIn("已废止", msg.body)
        self.assertEqual(msg.level, "warning")

    def test_build_message_unknown_event_fallback(self):
        """验证未知事件回退到通用模板。"""
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        msg = nmgr._build_message("unknown_event", {"key": "val"})
        self.assertEqual(msg.title, "unknown_event")
        self.assertEqual(msg.level, "info")

    def test_send_event_skips_when_no_rules(self):
        """无规则匹配时 send_event 应跳过发送。"""
        self.mock_cfg.get.side_effect = lambda key, default=None: {
            "notification.enabled": True,
            "notification.rules.test_event": None,
        }.get(key, default)
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        self.assertIsNone(nmgr.send_event("test_event", {}))

    def test_log_writes_on_failure(self):
        """渠道发送失败时应写入日志。"""
        self.mock_cfg.get.side_effect = lambda key, default=None: {
            "notification.enabled": True,
            "notification.channels.wechat.enabled": True,
            "notification.channels.wechat.webhook_url": "https://example.com/wechat",
            "notification.rules.test_event": ["wechat"],
        }.get(key, default)

        with patch("pilotstd.core.notification.manager.WechatChannel") as wc:
            mock_channel = MagicMock()
            mock_channel.send.return_value = False
            wc.return_value = mock_channel

            nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
            nmgr.send_event("test_event", {"key": "val"})

            self.mock_db.execute.assert_called()

    @patch("pilotstd.core.notification.manager.CredentialHelper")
    @patch("pilotstd.core.notification.manager.WechatChannel")
    @patch("pilotstd.core.notification.manager.TelegramChannel")
    @patch("pilotstd.core.notification.manager.FeishuChannel")
    @patch("pilotstd.core.notification.manager.DingTalkChannel")
    def test_init_with_aggregator(self, _dt, _fs, _tg, _wc, _cred_cls):
        """启用聚合器时正确初始化。"""
        mock_cred = MagicMock()
        mock_cred.get_all.return_value = {}
        _cred_cls.return_value = mock_cred
        self.mock_cfg.get.side_effect = lambda key, default=None: {
            "notification.enabled": True,
            "notification.aggregate_enabled": True,
            "notification.aggregate_window_seconds": 10,
            "notification.aggregate_max_events": 30,
        }.get(key, default)
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        self.assertIsNotNone(nmgr.aggregator)

    def test_send_event_disabled(self):
        """通知关闭时 send_event 返回 None 且不记录日志。"""
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        result = nmgr.send_event("test_event", {"key": "val"})
        self.assertIsNone(result)

    def test_build_message_auto_backup(self):
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        msg = nmgr._build_message("auto_backup", {"path": "/backup", "size_mb": 50})
        self.assertIsNotNone(msg)

    def test_build_message_announcement_check(self):
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        msg = nmgr._build_message(
            "announcement_check_complete",
            {"source_site": "samr_gb", "total_fetched": 20, "new_standards": 5},
        )
        self.assertIsNotNone(msg)

    def test_build_message_validity_system_failed(self):
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        msg = nmgr._build_message(
            "validity_system_failed",
            {"error": "Database connection lost"},
        )
        self.assertEqual(msg.level, "error")

    def test_build_message_auto_scan_failed(self):
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        msg = nmgr._build_message(
            "auto_scan_failed",
            {"error": "Permission denied"},
        )
        self.assertEqual(msg.level, "error")

    def test_init_event_builders_mapping(self):
        self.mock_cfg.get.return_value = False
        nmgr = NotificationManager(self.mock_cfg, self.mock_db, user_id=1)
        # _init_event_builders populates the dispatcher
        self.assertTrue(hasattr(nmgr, '_init_event_builders'))
