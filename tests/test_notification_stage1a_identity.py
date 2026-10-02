# tests/test_notification_stage1a_identity.py
"""阶段 1a（2026-10-02）：通知身份字段的**零行为变更**判据。

本批只做"加字段 + 加列"，因此必须能用断言证明三件事：

1. **旧 11 列逐列相等** —— 新增 4 列不改变 `notification_log` 既有列的取值；
2. **聚合路径不丢身份** —— `aggregate_buffer._send_merged` 是**重造**消息，
   未显式搬运的字段会取 dataclass 默认值（即聚合后 message_id 恒空）；
3. **补发路径不丢身份** —— `notification_queue.event_data` 的写入与重建用同一
   白名单，新字段不得在静音时段补发时被静默丢弃。

设计文档：docs/plans/notification-redesign/06-阶段0-1实施方案.md §2.2
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.notification.channel import NotificationMessage  # noqa: E402

# 既有 11 列（v17 建表 + is_read/aggregated_count/link/icon 追加），顺序即 INSERT 顺序
_LEGACY_COLUMNS = [
    "event_type",
    "channel",
    "title",
    "body",
    "standard_number",
    "status",
    "error_msg",
    "sent_at",
    "aggregated_count",
    "link",
    "icon",
]
# 阶段 1a 新增 4 列
_NEW_COLUMNS = ["message_id", "correlation_id", "delivery_status", "ack_status"]


class TestMessageDefaults(unittest.TestCase):
    """新字段的默认值必须等于"现状语义"（否则加字段就不是零行为变更）。"""

    def test_defaults(self):
        msg = NotificationMessage(title="t")
        self.assertEqual(msg.message_id, "")
        self.assertEqual(msg.correlation_id, "")
        self.assertEqual(msg.delivery_status, "pending")
        self.assertEqual(msg.ack_status, "none")

    def test_existing_fields_unchanged(self):
        """旧 13 个字段的默认值不得被本批改动（防手滑）。"""
        msg = NotificationMessage(title="t")
        self.assertEqual(msg.blocks, [])
        self.assertEqual(msg.body, "")
        self.assertEqual(msg.level, "info")
        self.assertIsNone(msg.standard_number)
        self.assertEqual(msg.event_type, "")
        self.assertIsNone(msg.link)
        self.assertIsNone(msg.icon)
        self.assertEqual(msg.aggregated_count, 1)
        self.assertEqual(msg.status, "")  # 业务结果态：本批**不动**
        self.assertEqual(msg.target_id, "")
        self.assertEqual(msg.elapsed_ms, 0)
        self.assertEqual(msg.changed_at, "")

    def test_status_and_delivery_status_are_distinct(self):
        """`status`（业务结果态）与 `delivery_status`（投递态）语义不同、互不赋值。"""
        msg = NotificationMessage(title="t", status="success")
        self.assertEqual(msg.status, "success")
        self.assertEqual(msg.delivery_status, "pending")


class TestLogInsertOldColumnsUnchanged(unittest.TestCase):
    """判据 1：同一输入下 `notification_log` 旧 11 列逐列相等。"""

    def _run_log(self, msg, status="success", error_msg="", sent_at="2026-10-02T10:00:00"):
        """跑一次 NotificationOps.log，返回 INSERT 的 (列名列表, 值元组)。"""
        from pilotstd.core.notification._manager_ops import NotificationOps

        db = MagicMock()
        mgr = MagicMock()
        mgr._db = db
        NotificationOps(mgr).log("archive_complete", "wechat", msg, status, error_msg, sent_at)
        sql, params = db.execute.call_args[0]
        cols = sql.split("(", 1)[1].split(")", 1)[0]
        return [c.strip() for c in cols.split(",")], params

    def test_columns_are_legacy_then_new(self):
        cols, params = self._run_log(NotificationMessage(title="T"))
        self.assertEqual(cols, _LEGACY_COLUMNS + _NEW_COLUMNS)
        self.assertEqual(len(params), 15)

    def test_legacy_eleven_values(self):
        msg = NotificationMessage(
            title="归档完成",
            body="已归档 3 个文件",
            level="info",
            standard_number="GB/T 1-2024",
            event_type="archive_complete",
            link="/standards/GB/T 1-2024",
            icon="pi pi-folder-open",
            aggregated_count=7,
        )
        cols, params = self._run_log(msg, status="failed", error_msg="boom")
        row = dict(zip(cols, params))
        # 旧 11 列逐列（is_read 不在 INSERT 内，靠列默认 0）
        self.assertEqual(row["event_type"], "archive_complete")
        self.assertEqual(row["channel"], "wechat")
        self.assertEqual(row["title"], "归档完成")
        self.assertEqual(row["body"], "已归档 3 个文件")
        self.assertEqual(row["standard_number"], "GB/T 1-2024")
        self.assertEqual(row["status"], "failed")  # 业务结果态取入参，不受新字段影响
        self.assertEqual(row["error_msg"], "boom")
        self.assertEqual(row["sent_at"], "2026-10-02T10:00:00")
        self.assertEqual(row["aggregated_count"], 7)
        self.assertEqual(row["link"], "/standards/GB/T 1-2024")
        self.assertEqual(row["icon"], "pi pi-folder-open")

    def test_new_columns_take_field_values(self):
        msg = NotificationMessage(
            title="T", message_id="abc123", correlation_id="run-1", delivery_status="sent", ack_status="read"
        )
        cols, params = self._run_log(msg)
        row = dict(zip(cols, params))
        self.assertEqual(row["message_id"], "abc123")
        self.assertEqual(row["correlation_id"], "run-1")
        self.assertEqual(row["delivery_status"], "sent")
        self.assertEqual(row["ack_status"], "read")

    def test_new_columns_default_when_absent(self):
        cols, params = self._run_log(NotificationMessage(title="T"))
        row = dict(zip(cols, params))
        self.assertEqual(row["message_id"], "")
        self.assertEqual(row["correlation_id"], "")
        self.assertEqual(row["delivery_status"], "pending")
        self.assertEqual(row["ack_status"], "none")


class TestMigrationV62(unittest.TestCase):
    """迁移 62：幂等追加 4 列，且不新增 `status` 列。"""

    def test_adds_four_columns_and_is_idempotent(self):
        from pilotstd.core.db._migrate_v62_notification_log_identity import (
            _migrate_v62_notification_log_identity,
        )

        db = MagicMock()
        _migrate_v62_notification_log_identity(db)
        sqls = [c[0][0] for c in db.execute.call_args_list]
        self.assertEqual(len(sqls), 4)
        joined = " ".join(sqls)
        for col in _NEW_COLUMNS:
            self.assertIn(f"ADD COLUMN {col}", joined)
        # 不得新增名为 status 的列（业务结果态语义）；注意 delivery_status/ack_status
        # 含子串 "status"，故必须按"ADD COLUMN status "整词匹配，不能用 in 判断
        self.assertNotIn("ADD COLUMN status ", joined)
        self.assertIn("ADD COLUMN delivery_status ", joined)
        self.assertIn("ADD COLUMN ack_status ", joined)

        # 幂等：列已存在（execute 抛错）时不得向外抛
        db2 = MagicMock()
        db2.execute.side_effect = Exception("duplicate column name")
        _migrate_v62_notification_log_identity(db2)  # 不抛即通过

    def test_schema_version_advanced(self):
        from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS

        self.assertEqual(CURRENT_SCHEMA_VERSION, 62)
        self.assertIn(62, MIGRATIONS, "v62 必须已注册（migrations.py 导入触发装饰器）")


if __name__ == "__main__":
    unittest.main()