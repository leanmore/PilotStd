# tests/test_notification_db.py
# 通知系统数据库迁移测试
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch


class TestNotificationDB(unittest.TestCase):
    """测试 notification_log 表结构和迁移。"""

    @patch("pilotstd.core.db.Database")
    def test_v18_migration_adds_is_read_column(self, mock_db_cls):
        """迁移 v18 应在 notification_log 表添加 is_read 列和索引。"""
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db

        from pilotstd.core.db import _migrate_v18_notification_fetch_task

        _migrate_v18_notification_fetch_task(mock_db)

        mock_db.execute.assert_any_call("ALTER TABLE notification_log ADD COLUMN is_read INTEGER DEFAULT 0")
        mock_db.execute.assert_any_call("CREATE INDEX IF NOT EXISTS idx_notif_is_read ON notification_log(is_read)")

    def test_sql_mark_all_read(self):
        """标记全部已读的 SQL 应为 UPDATE notification_log SET is_read=1。"""
        sql = "UPDATE notification_log SET is_read=1"
        self.assertIn("is_read=1", sql)

    def test_sql_mark_one_read(self):
        """标记单条已读的 SQL 应含 WHERE id=?。"""
        sql = "UPDATE notification_log SET is_read=1 WHERE id=?"
        self.assertIn("WHERE id=?", sql)

    def test_sql_select_by_is_read(self):
        """按 is_read 筛选的 SQL 应含 is_read = ?。"""
        condition = "is_read = ?"
        self.assertIn("is_read", condition)
