# tests/test_notification_api.py
# 通知系统 API 端点测试
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest


class TestNotificationAPI(unittest.TestCase):
    """测试通知 API 端点逻辑。"""

    def test_mark_read_request_model_default_id_none(self):
        """MarkReadRequest 的 id 默认应为 None。"""
        from docker.api.notification import MarkReadRequest

        req = MarkReadRequest()
        self.assertIsNone(req.id)

    def test_mark_read_request_model_with_id(self):
        """MarkReadRequest 接受指定的 id。"""
        from docker.api.notification import MarkReadRequest

        req = MarkReadRequest(id=42)
        self.assertEqual(req.id, 42)

    def test_mark_all_read_response_format(self):
        """标记全部已读应返回 ok: True。"""
        response = {"ok": True, "message": "已标记为已读"}
        self.assertTrue(response["ok"])
        self.assertIn("已标记为已读", response["message"])

    def test_mark_single_read_not_found_response(self):
        """标记不存在的 ID 应返回 404。"""
        response = {"error": "通知 ID 999 不存在"}
        self.assertIn("不存在", response["error"])

    def test_logs_response_includes_is_read_field(self):
        """logs 返回的 items 应包含 is_read 字段。"""
        items = [
            {
                "id": 1,
                "event_type": "test",
                "channel": "wechat",
                "title": "Test",
                "body": "Hello",
                "standard_number": None,
                "status": "success",
                "error_msg": None,
                "sent_at": "2026-06-29T12:00:00",
                "is_read": 0,
            }
        ]
        self.assertIn("is_read", items[0])
        self.assertEqual(items[0]["is_read"], 0)


class TestUpdateConfigSync(unittest.TestCase):
    """阶段一：PUT /api/notification/config 更新 enabled 时同时写 config.json 与 user_preferences。"""

    def _make_mgr(self):
        from unittest.mock import MagicMock

        mgr = MagicMock()
        mgr.cfg = MagicMock()
        mgr.user_service = MagicMock()
        mgr.notification_mgr = MagicMock()
        return mgr

    def test_enabled_writes_both_config_and_db(self):
        from unittest.mock import MagicMock

        from docker.api.notification import update_config

        mgr = self._make_mgr()
        result = update_config(request=MagicMock(), body={"enabled": True}, mgr=mgr, user_id=1)
        mgr.cfg.set.assert_called_once_with("notification.enabled", True)
        mgr.user_service.save_preference.assert_called_once_with(1, "notification.enabled", True)
        mgr.cfg.save.assert_called_once()
        mgr._init_notification.assert_called_once()
        self.assertEqual(result, {"ok": True})

    def test_enabled_false_writes_db(self):
        from unittest.mock import MagicMock

        from docker.api.notification import update_config

        mgr = self._make_mgr()
        update_config(request=MagicMock(), body={"enabled": False}, mgr=mgr, user_id=2)
        mgr.user_service.save_preference.assert_called_once_with(2, "notification.enabled", False)

    def test_db_write_failure_does_not_block(self):
        from unittest.mock import MagicMock

        from docker.api.notification import update_config

        mgr = self._make_mgr()
        mgr.user_service.save_preference.side_effect = RuntimeError("db down")
        result = update_config(request=MagicMock(), body={"enabled": True}, mgr=mgr, user_id=1)
        mgr.cfg.set.assert_called_once_with("notification.enabled", True)
        mgr._init_notification.assert_called_once()
        self.assertEqual(result, {"ok": True})
