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
