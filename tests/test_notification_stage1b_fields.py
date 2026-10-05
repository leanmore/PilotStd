# tests/test_notification_stage1b_fields.py
"""阶段 1b（2026-10-02）：任务视角字段（`task_id`/`notify_event`/`content_type`/`task_context`）。

沿用 1a 的判据骨架（旧 11 列相等 / 聚合搬运 / 补发白名单 / 迁移幂等），
并针对本批**唯一非标量字段 `task_context`** 新增三类边界判据：

1. **往返保真** —— dict → 落库(JSON 文本) → 读回 → 结构/类型/值全等（含嵌套与 Unicode）；
2. **空值区分** —— `{}` 与 `None` 在读回后**不可区分**（都回退 `{}`）。这是**显式约定**，
   本文件把它钉成契约，避免后人误以为能区分；
3. **非法输入** —— 非 dict（`"abc"`/`123`/`[1,2]`）、不可序列化对象：**一律回退 `{}`，绝不抛**。
   理由：通知是旁路链路，格式异常不得吃掉整条通知（详见 `_json_codec` 模块 docstring）。

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

from pilotstd.core.notification import _json_codec  # noqa: E402
from pilotstd.core.notification.channel import NotificationMessage  # noqa: E402

# 既有 11 列（顺序即 INSERT 顺序）——1a/1b 都必须保证其顺序与取值不变
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
# 阶段 1a 的 4 列
_STAGE_1A_COLUMNS = ["message_id", "correlation_id", "delivery_status", "ack_status"]
# 阶段 1b 的 4 列
_STAGE_1B_COLUMNS = ["task_id", "notify_event", "content_type", "task_context"]

# 往返保真用例：嵌套 + 类型混合 + Unicode + 空容器
_RICH_CONTEXT = {
    "a": 1,
    "nested": {"b": [1, 2, 3]},
    "unicode": "标准",
    "flag": True,
    "ratio": 1.5,
    "empty_list": [],
    "empty_dict": {},
    "null": None,
}


class TestMessageDefaults1b(unittest.TestCase):
    """新字段默认值 = 现状语义；既有 17 个字段不受影响。"""

    def test_defaults(self):
        msg = NotificationMessage(title="t")
        self.assertEqual(msg.task_id, "")
        self.assertEqual(msg.notify_event, "")
        self.assertEqual(msg.content_type, "")
        self.assertEqual(msg.task_context, {})

    def test_task_context_is_not_shared_between_instances(self):
        """★ default_factory 而非字面量 {}：两个实例不得共享同一个可变 dict。"""
        a = NotificationMessage(title="a")
        b = NotificationMessage(title="b")
        a.task_context["x"] = 1
        self.assertEqual(b.task_context, {}, "实例间共享了同一个 dict（可变默认值缺陷）")

    def test_stage_1a_fields_unchanged(self):
        msg = NotificationMessage(title="t")
        self.assertEqual(msg.message_id, "")
        self.assertEqual(msg.correlation_id, "")
        self.assertEqual(msg.delivery_status, "pending")
        self.assertEqual(msg.ack_status, "none")
        self.assertEqual(msg.status, "")  # 业务结果态：仍未动


class TestJsonCodecBoundaries(unittest.TestCase):
    """判据：往返保真 / 空值不可区分 / 非法输入不抛。"""

    def test_round_trip_fidelity(self):
        """★ 往返保真：结构、类型、值全等。"""
        text = _json_codec.dumps(_RICH_CONTEXT)
        self.assertIsInstance(text, str)
        self.assertEqual(_json_codec.loads_dict(text), _RICH_CONTEXT)

    def test_unicode_not_escaped_in_storage(self):
        """中文不转义入库（便于人工排查库内容）。"""
        text = _json_codec.dumps({"unicode": "标准"})
        self.assertIn("标准", text)

    def test_empty_and_none_are_indistinguishable(self):
        """★ 显式约定：{} 与 None 都落成空槽，读回都是 {}（**不可区分**）。

        注意空串**不在**此列：`dumps("")` 是"把一个空字符串作为值序列化"（→ `'""'`），
        与"空槽"是两回事；空槽是 `""` 这个**库内表征**，由 `dumps(None/空dict)` 产出。
        """
        for value in ({}, None):
            with self.subTest(value=repr(value)):
                stored = _json_codec.dumps(value)
                self.assertEqual(stored, "", "空槽统一为空串")
                self.assertEqual(_json_codec.loads_dict(stored), {})
        # 空字符串是**值**不是空槽：序列化为 JSON 字符串，读回不是 dict → 回退 {}
        self.assertEqual(_json_codec.dumps(""), '""')
        self.assertEqual(_json_codec.loads_dict('""'), {})

    def test_non_dict_json_text_falls_back(self):
        """非 dict 的合法 JSON（数组/数字/字符串）→ 回退 {}，不抛。"""
        for raw in ('[1, 2]', "123", '"abc"', "null", "true"):
            with self.subTest(raw=raw):
                self.assertEqual(_json_codec.loads_dict(raw), {})

    def test_malformed_text_falls_back(self):
        """非法 JSON → 回退 {}，且必须留下 warning（否则格式异常无声无息）。"""
        with self.assertLogs("pilotstd.core.notification._json_codec", level="WARNING"):
            self.assertEqual(_json_codec.loads_dict("{not json"), {})
        self.assertEqual(_json_codec.loads_dict("   "), {})

    def test_non_serializable_value_does_not_raise(self):
        """★ 非法输入：不可序列化对象 → 空槽 + warning，绝不抛（旁路链路不得因格式异常断链）。"""
        with self.assertLogs("pilotstd.core.notification._json_codec", level="WARNING"):
            self.assertEqual(_json_codec.dumps({"fn": object()}), "")

    def test_non_dict_input_types_fall_back(self):
        """写入侧收到非 dict（如 "abc" / 123）→ 被序列化成合法 JSON 文本，
        读取侧再保证只还原 dict；故非法输入不会污染 `task_context` 的 dict 契约。"""
        self.assertEqual(_json_codec.loads_dict(_json_codec.dumps("abc")), {})
        self.assertEqual(_json_codec.loads_dict(_json_codec.dumps(123)), {})

    def test_default_none_distinguishes_missing_key(self):
        """已废弃的哨兵设计（保留为负向断言）：**不再**存在"缺键 → None"的区分口径。

        1b 实现过程中曾用 `default=None` 做哨兵，但该设计自相矛盾——同一入参
        （空串）按"空槽"该给 {}、按"缺键"该给 None，无法两全。现统一为 `{}`，
        本用例钉死"不返回 None"这一约定，防止哨兵设计回潮。
        """
        self.assertEqual(_json_codec.loads_dict(None), {})
        self.assertEqual(_json_codec.loads_dict(""), {})
        self.assertEqual(_json_codec.loads_dict('{"a": 1}'), {"a": 1})
        # 三个入参都不得返回 None（字段类型必须恒为 dict）
        for raw in (None, "", "  ", "{not json", "[1]"):
            self.assertIsInstance(_json_codec.loads_dict(raw), dict)


class TestLogInsert1b(unittest.TestCase):
    """判据：旧 11 列逐列相等 + 1a 列保持 + 1b 列落库（task_context 转 JSON）。"""

    def _run_log(self, msg):
        from pilotstd.core.notification._manager_ops import NotificationOps

        db = MagicMock()
        mgr = MagicMock()
        mgr._db = db
        NotificationOps(mgr).log("archive_complete", "wechat", msg, "success", "", "2026-10-02T10:00:00")
        sql, params = db.execute.call_args[0]
        cols = [c.strip() for c in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
        return cols, params

    def test_legacy_prefix_unchanged(self):
        cols, params = self._run_log(NotificationMessage(title="T"))
        self.assertEqual(cols[:11], _LEGACY_COLUMNS)
        for col in _STAGE_1A_COLUMNS + _STAGE_1B_COLUMNS:
            self.assertIn(col, cols)
        self.assertEqual(len(params), len(cols))

    def test_legacy_eleven_values_unchanged(self):
        msg = NotificationMessage(
            title="归档完成",
            body="已归档 3 个文件",
            standard_number="GB/T 1-2024",
            event_type="archive_complete",
            link="/standards/GB/T 1-2024",
            icon="pi pi-folder-open",
            aggregated_count=7,
        )
        cols, params = self._run_log(msg)
        row = dict(zip(cols, params))
        self.assertEqual(row["event_type"], "archive_complete")
        self.assertEqual(row["title"], "归档完成")
        self.assertEqual(row["body"], "已归档 3 个文件")
        self.assertEqual(row["standard_number"], "GB/T 1-2024")
        self.assertEqual(row["status"], "success")
        self.assertEqual(row["aggregated_count"], 7)
        self.assertEqual(row["link"], "/standards/GB/T 1-2024")
        self.assertEqual(row["icon"], "pi pi-folder-open")

    def test_task_columns_written(self):
        msg = NotificationMessage(
            title="T",
            task_id="t-1",
            notify_event="task_lifecycle",
            content_type="list",
            task_context=_RICH_CONTEXT,
        )
        cols, params = self._run_log(msg)
        row = dict(zip(cols, params))
        self.assertEqual(row["task_id"], "t-1")
        self.assertEqual(row["notify_event"], "task_lifecycle")
        self.assertEqual(row["content_type"], "list")
        # task_context 落库为 JSON 文本，且往返后与原值全等
        self.assertIsInstance(row["task_context"], str)
        self.assertEqual(json.loads(row["task_context"]), _RICH_CONTEXT)

    def test_empty_context_stored_as_empty_slot(self):
        cols, params = self._run_log(NotificationMessage(title="T"))
        row = dict(zip(cols, params))
        self.assertEqual(row["task_context"], "")
        self.assertEqual(_json_codec.loads_dict(row["task_context"]), {})


class TestAggregatorCarriesTaskView(unittest.TestCase):
    """判据：聚合搬运（task_id/notify_event/content_type 取首条；task_context 取首条副本）。"""

    def _aggregate(self, msgs):
        from pilotstd.core.notification.aggregate_buffer import NotificationAggregator

        sent: list[NotificationMessage] = []
        agg = NotificationAggregator(lambda m, _ch: sent.append(m), window_seconds=60, batch_size=50)
        for m in msgs:
            agg.enqueue(m, ["wechat"], target_id=m.target_id)
        # 2026-10-05 分组键分层后：②路径的键以 **notify_event**（为空则 event_type）为收敛类，
        # 因此刷新必须按"收敛类"而不是 event_type（否则 notify_event 非空时找不到桶 ⇒ 不发送）。
        agg.flush(getattr(msgs[0], "notify_event", "") or msgs[0].event_type, msgs[0].target_id)
        return sent

    def test_merged_carries_task_view_from_first(self):
        msgs = [
            NotificationMessage(
                title="扫描完成",
                event_type="scan_complete",
                target_id="std-1",
                task_id="t-9",
                notify_event="task_lifecycle",
                content_type="list",
                task_context={"stage": "scan", "total": 3},
            )
            for _ in range(2)
        ]
        sent = self._aggregate(msgs)
        self.assertEqual(len(sent), 1)
        merged = sent[0]
        self.assertEqual(merged.task_id, "t-9")
        self.assertEqual(merged.notify_event, "task_lifecycle")
        self.assertEqual(merged.content_type, "list")
        self.assertEqual(merged.task_context, {"stage": "scan", "total": 3})

    def test_task_context_is_copied_not_shared(self):
        """★ 合并消息的 task_context 必须是副本：首条消息可能被调用方继续复用/修改。"""
        original = NotificationMessage(
            title="扫描完成",
            event_type="scan_complete",
            target_id="s",
            task_context={"k": "v"},
        )
        sent = self._aggregate([original])
        merged = sent[0]
        self.assertEqual(merged.task_context, {"k": "v"})
        self.assertIsNot(merged.task_context, original.task_context, "task_context 被共享而非拷贝")
        original.task_context["k"] = "changed"
        self.assertEqual(merged.task_context, {"k": "v"}, "改动原消息污染了合并消息")

    def test_merged_without_task_view_still_safe(self):
        msgs = [NotificationMessage(title="T", event_type="scan_empty", target_id="s", body=f"b{i}") for i in range(2)]
        sent = self._aggregate(msgs)
        self.assertEqual(sent[0].task_id, "")
        self.assertEqual(sent[0].notify_event, "")
        self.assertEqual(sent[0].content_type, "")
        self.assertEqual(sent[0].task_context, {})
class TestQueueJsonRoundTrip(unittest.TestCase):
    """判据：补发路径（序列化 → 反序列化）4 个 1b 字段不丢，task_context 走 JSON。"""

    def _manager(self):
        from pilotstd.core.notification.manager import NotificationManager
        from tests.fixtures.engine_mock_tree import ConfigStub

        cfg = ConfigStub({"notification.enabled": False, "notification.aggregate_enabled": False})
        db = MagicMock()
        db.fetchone.return_value = None
        db.fetchall.return_value = []
        return NotificationManager(cfg, db, 1), db

    def test_scalar_fields_in_whitelist_context_not(self):
        """task_context 是 dict，**不**进标量白名单（由 _json_codec 单独处理）。"""
        from pilotstd.core.notification.manager import _QUEUE_MESSAGE_FIELDS

        for field in ("task_id", "notify_event", "content_type"):
            self.assertIn(field, _QUEUE_MESSAGE_FIELDS, f"{field} 必须在补发白名单内")
        self.assertNotIn("task_context", _QUEUE_MESSAGE_FIELDS)

    def test_enqueue_writes_task_view(self):
        mgr, db = self._manager()
        mgr._cfg = MagicMock()
        mgr._cfg.get.return_value = "07:00"
        msg = NotificationMessage(
            title="T",
            event_type="scan_complete",
            task_id="t-1",
            notify_event="task_lifecycle",
            content_type="list",
            task_context=_RICH_CONTEXT,
        )
        mgr._enqueue_notification(msg, ["wechat"])

        _sql, params = db.execute.call_args[0]
        event_data = json.loads(params[1])
        self.assertEqual(event_data["task_id"], "t-1")
        self.assertEqual(event_data["notify_event"], "task_lifecycle")
        self.assertEqual(event_data["content_type"], "list")
        # 队列里的 task_context 是 JSON 文本（不是嵌套 dict）
        self.assertIsInstance(event_data["task_context"], str)

    def test_release_restores_task_view(self):
        """★ 核心：写侧产出的事件数据形状 → 补发还原，逐字段相等（含嵌套上下文）。"""
        mgr, db = self._manager()
        captured: list[NotificationMessage] = []
        mgr._send_now = lambda m, ch: captured.append(m)  # type: ignore[method-assign]

        event_data = {
            "event_type": "scan_complete",
            "title": "T",
            "body": "b",
            "level": "info",
            "link": None,
            "icon": None,
            "message_id": "",
            "correlation_id": "",
            "delivery_status": "suppressed",
            "ack_status": "none",
            "task_id": "t-1",
            "notify_event": "task_lifecycle",
            "content_type": "list",
            "task_context": _json_codec.dumps(_RICH_CONTEXT),
            "channels": ["wechat"],
        }
        db.fetchall.return_value = [{"id": 1, "event_type": "scan_complete", "event_data": json.dumps(event_data)}]

        self.assertEqual(mgr.release_suppressed_notifications(), 1)
        restored = captured[0]
        self.assertEqual(restored.task_id, "t-1")
        self.assertEqual(restored.notify_event, "task_lifecycle")
        self.assertEqual(restored.content_type, "list")
        self.assertEqual(restored.task_context, _RICH_CONTEXT, "★ 往返保真失败")

    def test_release_tolerates_legacy_rows_without_task_context(self):
        """旧队列数据（无 task_context 键）→ 空字典，且**不是 None**。"""
        mgr, db = self._manager()
        captured: list[NotificationMessage] = []
        mgr._send_now = lambda m, ch: captured.append(m)  # type: ignore[method-assign]

        legacy = {"event_type": "scan_empty", "title": "T", "body": "", "level": "info", "channels": []}
        db.fetchall.return_value = [{"id": 2, "event_type": "scan_empty", "event_data": json.dumps(legacy)}]

        self.assertEqual(mgr.release_suppressed_notifications(), 1)
        self.assertEqual(captured[0].task_context, {})
        self.assertIsInstance(captured[0].task_context, dict)

    def test_release_tolerates_corrupted_task_context(self):
        """★ 非法 JSON 入库（历史/外部写入）→ 回退 {}，不抛，通知照发。"""
        mgr, db = self._manager()
        captured: list[NotificationMessage] = []
        mgr._send_now = lambda m, ch: captured.append(m)  # type: ignore[method-assign]

        event_data = {
            "event_type": "scan_empty",
            "title": "T",
            "body": "",
            "level": "info",
            "task_context": "{not json",
            "channels": [],
        }
        db.fetchall.return_value = [{"id": 3, "event_type": "scan_empty", "event_data": json.dumps(event_data)}]

        with self.assertLogs("pilotstd.core.notification._json_codec", level="WARNING"):
            self.assertEqual(mgr.release_suppressed_notifications(), 1)
        self.assertEqual(captured[0].task_context, {})


class TestMigrationV63(unittest.TestCase):
    """迁移 63：幂等追加 4 列，task_context 为 TEXT，不新增 status 列。"""

    def test_adds_four_columns_and_is_idempotent(self):
        from pilotstd.core.db._migrate_v63_notification_log_task_view import (
            _migrate_v63_notification_log_task_view,
        )

        db = MagicMock()
        _migrate_v63_notification_log_task_view(db)
        sqls = [c[0][0] for c in db.execute.call_args_list]
        self.assertEqual(len(sqls), 4)
        joined = " ".join(sqls)
        for col in _STAGE_1B_COLUMNS:
            self.assertIn(f"ADD COLUMN {col}", joined)
        self.assertIn("task_context TEXT", joined)
        self.assertNotIn("ADD COLUMN status ", joined)

        # 幂等：列已存在（execute 抛错）时不得向外抛
        db2 = MagicMock()
        db2.execute.side_effect = Exception("duplicate column name")
        _migrate_v63_notification_log_task_view(db2)

    def test_schema_version_advanced_and_registered(self):
        from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS

        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 63)
        self.assertIn(63, MIGRATIONS, "v63 必须已注册（migrations.py 导入触发装饰器）")

    def test_no_stale_hard_assertion_in_codebase(self):
        """★ 防回归：不得出现"恰好等于某个版本号"的硬断言（1a 曾因此假红）。

        判定口径（三条同时满足才算断言）：
        1. 行内出现 `CURRENT_SCHEMA_VERSION ==`；
        2. `==` 后紧跟数字；
        3. **该行不含 CJK 字符** —— 本仓代码标识符/断言均为 ASCII，注释与 docstring 才含中文。
           这条把"说明文字里引用了 `CURRENT_SCHEMA_VERSION == 58`"这类散文准确排除
           （实测仓内有 5 处此类散文：v58/v59 模块 docstring、v61 的说明注释、本文件自身）。

        已知局限（有意接受）：启发式不解析 AST，故"纯 ASCII 的散文恰好写出
        `CURRENT_SCHEMA_VERSION == 64`"会误报。接受的理由——该形态在本仓从未出现，
        而 AST 版需处理 docstring/注释归属，复杂度不成比例；真误报时改那句散文即可。
        """
        offenders: list[str] = []
        for path in list(Path("tests").rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                marker = "CURRENT_SCHEMA_VERSION =="
                pos = stripped.find(marker)
                if pos < 0:
                    continue
                tail = stripped[pos + len(marker) :].lstrip()
                if not tail[:1].isdigit():
                    continue
                if any("\u4e00" <= ch <= "\u9fff" for ch in stripped):
                    continue  # 含中文 → 注释/docstring 散文，非断言
                offenders.append(f"{path}:{i}")
        self.assertEqual(offenders, [], f"存在硬断言版本号（会随每次加迁移假红）: {offenders}")


if __name__ == "__main__":
    unittest.main()
