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

import json
import os
import sys
import unittest
from pathlib import Path
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
        """★ 零行为变更的核心：**前 11 列**必须仍是既有列且顺序不变。

        后续批次会继续追加列（1b 已追加 4 列），故这里只锁前缀，
        不锁总列数——锁总列数会让每批加字段都假红。
        """
        cols, params = self._run_log(NotificationMessage(title="T"))
        self.assertEqual(cols[:11], _LEGACY_COLUMNS, "前 11 列必须是既有列且顺序不变")
        for col in _NEW_COLUMNS:
            self.assertIn(col, cols, f"{col} 必须已加入 INSERT")
        self.assertEqual(len(params), len(cols))

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
        """v62 已注册且版本号已推进到至少 62。

        不断言"恰好等于 62"——该值随每批新迁移推进（1b 已到 63）；
        "当前版本号 == 已注册最大号"由 tests/test_migrations_full.py 负责。
        """
        from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS

        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 62)
        self.assertIn(62, MIGRATIONS, "v62 必须已注册（migrations.py 导入触发装饰器）")


class TestAggregatorCarriesIdentity(unittest.TestCase):
    """判据 2：聚合两条带 correlation_id 的消息 → merged 的身份字段非空。"""

    def _aggregate(self, msgs):
        from pilotstd.core.notification.aggregate_buffer import NotificationAggregator

        sent: list[NotificationMessage] = []
        agg = NotificationAggregator(lambda m, _ch: sent.append(m), window_seconds=60, batch_size=50)
        for m in msgs:
            agg.enqueue(m, ["wechat"], target_id=m.target_id)
        agg.flush(msgs[0].event_type, msgs[0].target_id)
        return sent

    def test_single_message_keeps_identity(self):
        msg = NotificationMessage(
            title="扫描完成",
            event_type="scan_complete",
            message_id="m-1",
            correlation_id="run-9",
            delivery_status="sent",
            ack_status="read",
        )
        sent = self._aggregate([msg])
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].message_id, "m-1")
        self.assertEqual(sent[0].correlation_id, "run-9")

    def test_merged_keeps_group_identity_and_resets_delivery(self):
        """多条聚合：身份取首条；投递态/回执态**重置**（这条消息尚未投递）。"""
        msgs = [
            NotificationMessage(
                title="扫描完成",
                event_type="scan_complete",
                target_id="std-1",
                message_id=f"m-{i}",
                correlation_id="run-9",
                delivery_status="sent",
                ack_status="read",
            )
            for i in (1, 2, 3)
        ]
        sent = self._aggregate(msgs)
        self.assertEqual(len(sent), 1)
        merged = sent[0]
        self.assertEqual(merged.aggregated_count, 3)
        self.assertEqual(merged.message_id, "m-1", "合并消息的身份应取首条")
        self.assertEqual(merged.correlation_id, "run-9", "★ 聚合后 correlation_id 不得丢失")
        self.assertEqual(merged.delivery_status, "pending", "重造的消息尚未投递，不得沿用 sent")
        self.assertEqual(merged.ack_status, "none")

    def test_merged_without_identity_still_safe(self):
        """旧调用方不带身份时聚合不得报错（默认值兜底）。"""
        msgs = [
            NotificationMessage(title="扫描完成", event_type="scan_complete", target_id="s", body=f"b{i}")
            for i in range(2)
        ]
        sent = self._aggregate(msgs)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].message_id, "")
        self.assertEqual(sent[0].correlation_id, "")
        self.assertEqual(sent[0].delivery_status, "pending")


class TestSuppressedQueueFieldRoundTrip(unittest.TestCase):
    """判据 3：静音补发路径（序列化 → 反序列化）4 个新字段不丢。"""

    def _manager(self):
        from pilotstd.core.notification.manager import NotificationManager
        from tests.fixtures.engine_mock_tree import ConfigStub

        cfg = ConfigStub({"notification.enabled": False, "notification.aggregate_enabled": False})
        db = MagicMock()
        db.fetchone.return_value = None
        db.fetchall.return_value = []
        return NotificationManager(cfg, db, 1), db

    def test_write_and_rebuild_share_whitelist(self):
        """写入键集合 ⊆ 白名单 → 否则重建侧拿不到（白名单比写入宽是可以的）。"""
        from pilotstd.core.notification.manager import _QUEUE_MESSAGE_FIELDS

        for field in _NEW_COLUMNS:
            self.assertIn(field, _QUEUE_MESSAGE_FIELDS, f"{field} 必须在补发白名单内")

    def test_enqueue_writes_identity_fields(self):
        mgr, db = self._manager()
        mgr._cfg = MagicMock()
        mgr._cfg.get.return_value = "07:00"
        msg = NotificationMessage(
            title="扫描完成",
            body="b",
            event_type="scan_complete",
            message_id="m-42",
            correlation_id="run-7",
            delivery_status="sent",
            ack_status="delivered",
        )
        mgr._enqueue_notification(msg, ["wechat"])

        insert_sql, insert_params = db.execute.call_args[0]
        self.assertIn("notification_queue", insert_sql)
        event_data = json.loads(insert_params[1])
        self.assertEqual(event_data["message_id"], "m-42")
        self.assertEqual(event_data["correlation_id"], "run-7")
        self.assertEqual(event_data["delivery_status"], "sent")
        self.assertEqual(event_data["ack_status"], "delivered")

    def test_release_restores_identity_fields(self):
        """★ 核心：从 event_data 重建的消息，4 个新字段必须原样回来。"""
        mgr, db = self._manager()
        captured: list[NotificationMessage] = []
        mgr._send_now = lambda m, ch: captured.append(m)  # type: ignore[method-assign]

        event_data = {
            "event_type": "scan_complete",
            "title": "扫描完成",
            "body": "b",
            "level": "info",
            "link": None,
            "icon": None,
            "message_id": "m-42",
            "correlation_id": "run-7",
            "delivery_status": "suppressed",
            "ack_status": "none",
            "channels": ["wechat"],
        }
        db.fetchall.return_value = [{"id": 1, "event_type": "scan_complete", "event_data": json.dumps(event_data)}]

        count = mgr.release_suppressed_notifications()

        self.assertEqual(count, 1)
        self.assertEqual(len(captured), 1)
        restored = captured[0]
        self.assertEqual(restored.message_id, "m-42")
        self.assertEqual(restored.correlation_id, "run-7")
        self.assertEqual(restored.delivery_status, "suppressed")
        self.assertEqual(restored.ack_status, "none")
        # 旧字段同时不得丢（回归）
        self.assertEqual(restored.title, "扫描完成")
        self.assertEqual(restored.event_type, "scan_complete")

    def test_release_tolerates_missing_new_fields(self):
        """旧队列数据（无新字段）补发不得报错——走 dataclass 默认值。"""
        mgr, db = self._manager()
        captured: list[NotificationMessage] = []
        mgr._send_now = lambda m, ch: captured.append(m)  # type: ignore[method-assign]

        legacy = {"event_type": "scan_empty", "title": "扫描完成", "body": "", "level": "info", "channels": []}
        db.fetchall.return_value = [{"id": 2, "event_type": "scan_empty", "event_data": json.dumps(legacy)}]

        self.assertEqual(mgr.release_suppressed_notifications(), 1)
        self.assertEqual(captured[0].message_id, "")
        self.assertEqual(captured[0].delivery_status, "pending")


class TestFacadeUserIdInjection(unittest.TestCase):
    """阶段 1a 顺手项：通知收件人改构造时注入，**默认仍为 1**（裁决 Q6：技术债，非阻塞）。

    验证方式：把 BaseFacade 的重活初始化全桩掉，只跑 __init__ 的编排，
    捕获 _init_services/_init_notification 传给 NotificationManager 的 user_id。
    """

    def _run(self, **ctor_kwargs):
        from unittest.mock import patch

        from pilotstd.manager.facade._base import BaseFacade

        fake_core = MagicMock()
        fake_cfg = MagicMock()
        fake_db = MagicMock()
        captured: list[dict] = []

        def fake_notification_manager(*args, **kwargs):
            captured.append(kwargs)
            return MagicMock()

        with (
            patch("pilotstd.manager.facade._base.ManagerCore", return_value=fake_core),
            patch.object(BaseFacade, "_init_config_and_scanner", return_value=None),
            patch.object(BaseFacade, "_init_query_subsystem", return_value=None),
            patch.object(BaseFacade, "_init_download", return_value=None),
            patch.object(BaseFacade, "_init_services", autospec=True) as init_services,
            patch.object(BaseFacade, "_bind_methods", return_value=None),
            patch("pilotstd.manager.facade._base.NotificationManager", side_effect=fake_notification_manager),
        ):
            init_services.side_effect = lambda self: BaseFacade._init_notification(self)
            facade = BaseFacade(fake_cfg, fake_db, user_id=ctor_kwargs.get("user_id", 1))
        return facade, captured

    def test_default_user_id_is_one(self):
        """不传 user_id 时默认 1（全部既有调用点零改动的前提）。"""
        facade, captured = self._run()
        self.assertEqual(facade._facade_user_id, 1)
        self.assertEqual(captured[-1]["user_id"], 1)

    def test_injected_user_id_is_forwarded(self):
        """显式注入时按注入值构造（为将来多用户留门）。"""
        facade, captured = self._run(user_id=7)
        self.assertEqual(facade._facade_user_id, 7)
        self.assertEqual(captured[-1]["user_id"], 7)

    def test_no_hardcoded_user_id_remains(self):
        """★ 防回归：源码里不得再有硬编码 user_id=1 传给 NotificationManager。"""
        source = Path("pilotstd/manager/facade/_base.py").read_text(encoding="utf-8")
        self.assertNotIn("NotificationManager(self._core.cfg, self._core.db, user_id=1)", source)
        self.assertEqual(source.count("user_id=self._facade_user_id"), 2, "两处构造点都应注入")


if __name__ == "__main__":
    unittest.main()
