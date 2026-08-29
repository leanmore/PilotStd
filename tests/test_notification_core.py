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
        import pilotstd.core.notification._message_builders as _mb

        class _BuilderNS:
            pass
        self.mixin = _BuilderNS()
        # 将所有 _build_* 函数绑定到命名空间对象上
        for name in dir(_mb):
            if name.startswith("_build_"):
                setattr(self.mixin, name, getattr(_mb, name))

    def test_archive_complete_with_dirs(self):
        msg = self.mixin._build_archive_complete_message({"count": 5, "directories": ["d1", "d2", "d3", "d4", "d5"]})
        self.assertEqual(msg.level, "info")
        # blocks[0] 为 TextBlock("已归档 5 个目录"), blocks[1] 为 ListBlock
        self.assertIn("5", msg.blocks[0].text)

    def test_archive_complete_zero(self):
        msg = self.mixin._build_archive_complete_message({"count": 0, "directories": []})
        self.assertIn("已归档：0", msg.blocks[0].text)

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

    def test_status_changed_expired_has_changed_at(self):
        """standard_expired 已合并：is_expired=True 时含变更时间行（StatusChangeBlock + TextBlock）。"""
        msg = self.mixin._build_standard_status_changed_message({
            "standard_number": "GB/T 1.1",
            "old_status": "现行",
            "new_status": "已废止",
            "is_expired": True,
            "changed_at": "2026-01-15T10:00:00",
        })
        self.assertEqual(len(msg.blocks), 2)  # StatusChangeBlock + TextBlock(变更时间)
        self.assertEqual(msg.level, "error")

    def test_standard_first_registered(self):
        msg = self.mixin._build_standard_first_registered_message({"standard_number": "GB/T 1.1"})
        self.assertIsNotNone(msg)

    def test_batch_download_complete(self):
        msg = self.mixin._build_batch_download_complete_message({"count": 3, "failed": 0})
        self.assertEqual(msg.level, "info")

    def test_batch_download_with_failures(self):
        msg = self.mixin._build_batch_download_complete_message({"count": 5, "failed": 2})
        # 4 段式（v1.1）：统计压缩为单行 TextBlock，标题区分有/无失败
        self.assertIn("2", msg.blocks[0].text)
        self.assertEqual(msg.level, "warning")

    def test_worker_error(self):
        msg = self.mixin._build_worker_error_message(
            {"standard_number": "TEST", "error": "Connection refused", "source_site": "test"}
        )
        self.assertEqual(msg.level, "error")

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

    def test_announcement_fetch_complete_with_source(self):
        """含 source 字段时追加来源 Block。"""
        msg = self.mixin._build_announcement_fetch_complete_message(
            {"count": 10, "source": "ahbz"}
        )
        self.assertEqual(len(msg.blocks), 2)  # KeyValueBlock + TextBlock(source)

    def test_batch_query_summary_pending(self):
        """有 pending 时 level 升级为 warning。"""
        msg = self.mixin._build_batch_query_summary_message({
            "total": 5, "found": 3, "pending": 2,
        })
        self.assertEqual(msg.level, "warning")

    # ── 补充覆盖 _ValidityBuildersMixin 未覆盖路径 ──

    def test_first_registered_with_elapsed_ms(self):
        msg = self.mixin._build_standard_first_registered_message({
            "standard_number": "GB/T 1", "elapsed_ms": 1500,
        })
        self.assertEqual(len(msg.blocks), 3)  # TextBlock + ListBlock + TextBlock(窗口耗时)

    def test_validity_batch_report_empty(self):
        msg = self.mixin._build_validity_batch_report_message({
            "count": 0, "changed": 0, "failed": 0,
        })
        self.assertEqual(msg.level, "info")

    def test_validity_batch_report_with_adapter_status(self):
        msg = self.mixin._build_validity_batch_report_message({
            "count": 10, "changed": 2, "failed": 1, "adapter_status": "正常",
        })
        self.assertEqual(msg.level, "warning")

    def test_validity_round_summary_with_changes(self):
        msg = self.mixin._build_validity_round_summary_message({
            "round": 1, "total_checks": 100, "total_changes": 3,
            "total_failures": 0, "change_list": ["变更1", "变更2"],
        })
        self.assertEqual(msg.level, "info")

    def test_validity_system_failed_with_context(self):
        msg = self.mixin._build_validity_system_failed_message({
            "error": "db error", "context": "migration step 3",
        })
        self.assertEqual(msg.level, "error")
        self.assertEqual(len(msg.blocks), 2)

    def test_image_update_available(self):
        msg = self.mixin._build_image_update_available_message({"version": "2.0.0", "url": "https://..."})
        self.assertIsNotNone(msg)

    def test_trust_ip_update(self):
        msg = self.mixin._build_trust_ip_update_message({"ip": "192.168.1.1"})
        self.assertIsNotNone(msg)

    # ── 补充覆盖 _SystemBuildersMixin 剩余未覆盖路径 ──

    def test_auto_backup_success(self):
        msg = self.mixin._build_auto_backup_message({
            "success": True, "backup_path": "/backup/db.gz", "size_mb": "42.5",
        })
        self.assertEqual(msg.level, "info")
        self.assertEqual(len(msg.blocks), 2)

    def test_auto_backup_failed(self):
        msg = self.mixin._build_auto_backup_message({
            "success": False, "error": "disk full",
        })
        self.assertEqual(msg.level, "error")

    def test_announcement_check_with_source_and_failures(self):
        msg = self.mixin._build_announcement_check_complete_message({
            "source": "std_gov",
            "total_announcements": 10, "gb_count": 3, "hb_count": 5, "db_count": 2,
            "total_standards": 8, "failures": 2,
        })
        self.assertEqual(msg.level, "warning")  # 部分失败

    def test_announcement_check_all_success(self):
        msg = self.mixin._build_announcement_check_complete_message({
            "source": "std_gov",
            "total_announcements": 5, "gb_count": 3, "hb_count": 2, "db_count": 0,
            "total_standards": 5, "failures": 0,
        })
        self.assertEqual(msg.level, "info")  # 无失败

    def test_announcement_check_all_failed(self):
        msg = self.mixin._build_announcement_check_complete_message({
            "total_announcements": 0, "failures": 3,
        })
        self.assertEqual(msg.level, "error")  # 全部失败

    def test_image_update_error(self):
        msg = self.mixin._build_image_update_available_message({
            "error": "connection timeout",
        })
        self.assertEqual(msg.level, "error")

    def test_image_update_with_release_notes(self):
        msg = self.mixin._build_image_update_available_message({
            "old_digest": "abc", "new_digest": "def",
            "release_notes": "Bug fixes",
        })
        self.assertEqual(msg.level, "info")
        # 第三个 block 是 release_notes
        self.assertEqual(len(msg.blocks), 2)

    def test_worker_error_with_traceback(self):
        msg = self.mixin._build_worker_error_message({
            "worker": "Scanner", "error": "OOM", "traceback": "Traceback...",
        })
        self.assertEqual(msg.level, "error")
        self.assertEqual(len(msg.blocks), 3)  # title + error + traceback

    def test_task_execution_failed(self):
        msg = self.mixin._build_task_execution_failed_message({
            "task_name": "DailyScan", "error": "timeout",
        })
        self.assertEqual(msg.level, "error")
        # 新模板三行：任务 / 错误（翻译后）/ 重试提示
        self.assertEqual(len(msg.blocks), 3)

    def test_announcement_fetch_failed(self):
        msg = self.mixin._build_announcement_fetch_failed_message({
            "source": "ahbz", "error": "502 Bad Gateway",
        })
        self.assertEqual(msg.level, "error")

    def test_quota_exhausted(self):
        msg = self.mixin._build_quota_exhausted_message({
            "site_name": "std_gov", "quota_limit": "200", "reset_time": "明日 0:00",
        })
        self.assertEqual(msg.level, "warning")

    # ── 补充覆盖 _BatchBuildersMixin 剩余未覆盖方法 ──

    def test_auto_scan_failed(self):
        msg = self.mixin._build_auto_scan_failed_message({
            "path": "/data/scans", "error": "permission denied",
        })
        self.assertEqual(msg.level, "error")
        self.assertEqual(len(msg.blocks), 2)

    def test_download_failed(self):
        msg = self.mixin._build_download_failed_message({
            "standard_number": "GB/T 1", "error": "404",
        })
        self.assertEqual(msg.level, "error")

    def test_archive_abandoned(self):
        msg = self.mixin._build_archive_abandoned_message({
            "standard_info": "GB/T 1-2020", "error": "retry exhausted",
        })
        self.assertEqual(msg.level, "error")

    def test_normalize_complete(self):
        msg = self.mixin._build_normalize_complete_message({
            "total": 10, "success": 9, "failed": 1,
        })
        self.assertEqual(msg.level, "info")

    def test_scan_complete(self):
        msg = self.mixin._build_scan_complete_message({
            "count": 5, "failed": 1,
        })
        # 新模板：存在失败时升级为 warning
        self.assertEqual(msg.level, "warning")

    def test_scan_complete_zero(self):
        msg = self.mixin._build_scan_complete_message({
            "count": 0, "failed": 0,
        })
        self.assertEqual(msg.level, "info")

    def test_date_reminder(self):
        msg = self.mixin._build_date_reminder_message({
            "standard_number": "GB/T 1", "std_name": "测试标准",
            "days_before": 30, "remind_type": "实施日期前30天",
        })
        self.assertEqual(msg.level, "info")

    def test_scan_empty(self):
        msg = self.mixin._build_scan_empty_message({})
        self.assertEqual(msg.level, "info")

    def test_query_failed(self):
        msg = self.mixin._build_query_failed_message({
            "standard_number": "GB/T 1", "error": "timeout",
        })
        self.assertEqual(msg.level, "error")

    def test_query_empty(self):
        msg = self.mixin._build_query_empty_message({"total": 10})
        self.assertEqual(msg.level, "warning")

    def test_archive_failed(self):
        msg = self.mixin._build_archive_failed_message({
            "count": 5, "error": "disk full",
        })
        self.assertEqual(msg.level, "error")

    def test_normalize_failed(self):
        msg = self.mixin._build_normalize_failed_message({
            "total": 10, "error": "parse error",
        })
        self.assertEqual(msg.level, "error")

    def test_expire_standard_moved(self):
        msg = self.mixin._build_expire_standard_moved_message({
            "standard_number": "GB/T 1-2020",
            "target_path": "/archive/expired/",
        })
        self.assertEqual(msg.level, "info")

    def test_replacement_not_found_with_sources(self):
        msg = self.mixin._build_replacement_not_found_message({
            "standard_number": "GB/T 1",
            "searched_sources": ["std_gov", "ahbz"],
        })
        self.assertEqual(msg.level, "warning")

    def test_replacement_not_found_no_sources(self):
        msg = self.mixin._build_replacement_not_found_message({
            "standard_number": "GB/T 1",
        })
        self.assertEqual(msg.level, "warning")

    def test_announce_fetch_summary_success(self):
        msg = self.mixin._build_announce_fetch_summary_message({
            "adapters": [
                {"name": "ahbz", "status": "success", "count": 5},
                {"name": "std_gov", "status": "success", "count": 3},
            ],
            "total_count": 8,
            "has_error": False,
        })
        self.assertEqual(msg.level, "info")

    def test_announce_fetch_summary_with_errors(self):
        msg = self.mixin._build_announce_fetch_summary_message({
            "adapters": [
                {"name": "ahbz", "status": "success", "count": 5},
                {"name": "std_gov", "status": "failure", "error_msg": "timeout"},
            ],
            "total_count": 5,
            "has_error": True,
        })
        self.assertEqual(msg.level, "warning")

    def test_announce_fetch_summary_truncated(self):
        adapters = [
            {"name": f"site_{i}", "status": "success", "count": 1}
            for i in range(15)
        ]
        msg = self.mixin._build_announce_fetch_summary_message({
            "adapters": adapters,
            "total_count": 15,
            "has_error": False,
        })
        self.assertEqual(msg.level, "info")
        # 4 段式（v1.1）：明细截断阈值 5 → 1 total + 5 displayed + 1 "other"
        self.assertEqual(len(msg.blocks), 7)

    def test_batch_query_summary_with_results(self):
        msg = self.mixin._build_batch_query_summary_message({
            "total": 5, "found": 5, "pending": 0,
            "results": [
                {"number": "GB/T 1", "name": "标准1"},
                {"number": "GB/T 2", "name": "标准2"},
            ],
        })
        self.assertEqual(msg.level, "info")
        self.assertEqual(len(msg.blocks), 2)  # TextBlock + ListBlock


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
