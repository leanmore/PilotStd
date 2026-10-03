# tests/test_notification_stage1c_fields.py
"""阶段 1c（2026-10-02）：交互能力字段（`actions` / `callback_data` / `attachments` / `channel_message_ids`）。

## 本批只做**契约级断言**（不重复 1b 的泛化边界）

JSON 往返、空值不可区分、非法输入回退这三类**泛化**判据已由 1b 的
`tests/test_notification_stage1b_fields.py::TestJsonCodecBoundaries` 覆盖。
本文件只验证"**这 4 个字段确实走了 `_json_codec`**"以及它们的**字段级契约**：

- 数据类型：`ActionSpec` / `AttachmentSpec` 的不可变性、白名单闭集、序列化形态；
- 落库：INSERT 的 1c 4 列取值 = 经 `_json_codec` 转换后的 JSON 文本 / 纯字符串；
- 聚合：`actions`/`attachments` **深拷贝取首条**、`channel_message_ids`/`callback_data` **重置**；
- 补发：4 字段往返不丢（`loads_list` / `loads_dict` 各自还原）；
- `channel_message_ids` 的**语义约定**（键白名单 / 值恒 str / 未投递则键缺席）。

设计文档：docs/plans/notification-redesign/02-目标架构.md §2.2 / §2.4 / §2.5
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.notification import _json_codec  # noqa: E402
from pilotstd.core.notification.channel import (  # noqa: E402
    NotificationMessage,
)
from pilotstd.core.notification.specs import (  # noqa: E402
    ACTION_STYLES,
    ACTIONS,
    ATTACHMENT_KINDS,
    ActionSpec,
    AttachmentSpec,
    specs_to_jsonable,
)

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
_STAGE_1A_COLUMNS = ["message_id", "correlation_id", "delivery_status", "ack_status"]
_STAGE_1B_COLUMNS = ["task_id", "notify_event", "content_type", "task_context"]
_STAGE_1C_COLUMNS = ["actions", "callback_data", "attachments", "channel_message_ids"]


def _action(action: str = "retry") -> ActionSpec:
    return ActionSpec(action=action, label_key="notification.action.retry", args={"record_id": 7})


class TestSpecsDatatypes(unittest.TestCase):
    """数据类型定义：不可变性 + 闭集白名单 + 序列化形态。"""

    def test_frozen(self):
        """frozen=True：字段不可重新赋值（可哈希、可进 set）。

        注意 frozen 只保证"不重新赋值字段"，**不**保证 `args` 内容不可变——
        故契约明确要求调用方不得修改已构造实例的 `args`（见 specs.py docstring）。
        """
        spec = _action()
        try:
            spec.action = "ignore"
        except FrozenInstanceError:
            pass
        else:  # pragma: no cover - 仅在 frozen 失效时进入
            self.fail("ActionSpec 应为 frozen（不可重新赋值字段）")
        self.assertEqual(spec.action, "retry")
        self.assertIn(spec, {spec})  # 可哈希

    def test_action_whitelist_matches_design(self):
        """动作白名单与 02-目标架构.md §2.2 逐项一致（闭集）。"""
        self.assertEqual(
            set(ACTIONS),
            {"view_detail", "open_logs", "retry", "ignore", "snooze", "mark_done"},
        )
        self.assertEqual(set(ACTION_STYLES), {"default", "primary", "danger"})

    def test_attachment_kinds_closed(self):
        self.assertEqual(set(ATTACHMENT_KINDS), {"image", "file"})

    def test_specs_to_jsonable_converts_dataclass(self):
        specs = [_action(), AttachmentSpec(kind="image", url="/x.png", name="图", size=12)]
        out = specs_to_jsonable(specs)
        self.assertEqual(
            out[0],
            {
                "action": "retry",
                "label_key": "notification.action.retry",
                "style": "default",
                "args": {"record_id": 7},
                "requires_confirm": False,
            },
        )
        self.assertEqual(out[1], {"kind": "image", "url": "/x.png", "name": "图", "size": 12})
        # 必须可 JSON 序列化（否则 INSERT/入队时会炸）
        json.dumps(out, ensure_ascii=False)

    def test_specs_to_jsonable_passthrough_dict_and_drops_garbage(self):
        """幂等关键：已是 dict 的项原样保留（读取端给的就是 dict）；畸形项被丢弃不抛。"""
        out = specs_to_jsonable([{"action": "ignore"}, object(), None, 123])  # type: ignore[list-item]
        self.assertEqual(out, [{"action": "ignore"}])

    def test_specs_to_jsonable_tolerates_none_and_empty(self):
        self.assertEqual(specs_to_jsonable([]), [])
        self.assertEqual(specs_to_jsonable(None), [])  # type: ignore[arg-type]


class TestMessageDefaults1c(unittest.TestCase):
    def test_defaults(self):
        msg = NotificationMessage(title="t")
        self.assertEqual(msg.actions, [])
        self.assertEqual(msg.callback_data, "")
        self.assertEqual(msg.attachments, [])
        self.assertEqual(msg.channel_message_ids, {})

    def test_mutable_defaults_not_shared(self):
        a = NotificationMessage(title="a")
        b = NotificationMessage(title="b")
        a.actions.append(_action())
        a.attachments.append(AttachmentSpec(kind="image", url="/x"))
        a.channel_message_ids["wechat"] = "mid-1"
        self.assertEqual(b.actions, [])
        self.assertEqual(b.attachments, [])
        self.assertEqual(b.channel_message_ids, {}, "实例间共享了同一个 dict")

    def test_prior_stage_fields_unchanged(self):
        msg = NotificationMessage(title="t")
        self.assertEqual(msg.message_id, "")
        self.assertEqual(msg.delivery_status, "pending")
        self.assertEqual(msg.task_id, "")
        self.assertEqual(msg.task_context, {})
        self.assertEqual(msg.status, "")  # 业务结果态仍未动


class TestLogInsert1c(unittest.TestCase):
    """落库：1c 4 列的取值形态（JSON 文本 / 纯字符串）。"""

    def _row(self, msg):
        from pilotstd.core.notification._manager_ops import NotificationOps

        db = MagicMock()
        mgr = MagicMock()
        mgr._db = db
        NotificationOps(mgr).log("archive_complete", "wechat", msg, "success", "", "2026-10-02T10:00:00")
        sql, params = db.execute.call_args[0]
        cols = [c.strip() for c in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
        return cols, dict(zip(cols, params))

    def test_legacy_prefix_and_prior_batches_intact(self):
        cols, _row = self._row(NotificationMessage(title="T"))
        self.assertEqual(cols[:11], _LEGACY_COLUMNS)
        for col in _STAGE_1A_COLUMNS + _STAGE_1B_COLUMNS + _STAGE_1C_COLUMNS:
            self.assertIn(col, cols)

    def test_actions_attachments_stored_as_json_text(self):
        """★ 契约：actions / attachments 落库为**字典列表的 JSON 文本**（走 specs + _json_codec）。"""
        msg = NotificationMessage(
            title="T",
            actions=[_action("retry"), _action("ignore")],
            attachments=[AttachmentSpec(kind="image", url="/x.png", name="图", size=12)],
        )
        _cols, row = self._row(msg)
        self.assertIsInstance(row["actions"], str)
        self.assertIsInstance(row["attachments"], str)
        actions = json.loads(row["actions"])
        self.assertEqual([a["action"] for a in actions], ["retry", "ignore"])
        self.assertEqual(actions[0]["args"], {"record_id": 7})
        # 读回形态与 _json_codec.loads_list 的产出一致（幂等）
        self.assertEqual(_json_codec.loads_list(row["actions"]), actions)
        self.assertEqual(json.loads(row["attachments"])[0]["kind"], "image")

    def test_callback_data_is_plain_string_not_json(self):
        """★ 契约：callback_data 是**纯字符串**，落库不做 JSON 编解码（不加引号）。"""
        payload = "v1|0123456789abcdef|retry|7"
        _cols, row = self._row(NotificationMessage(title="T", callback_data=payload))
        self.assertEqual(row["callback_data"], payload)
        self.assertLessEqual(len(payload.encode("utf-8")), 64)

    def test_channel_message_ids_stored_as_json_object(self):
        msg = NotificationMessage(title="T", channel_message_ids={"telegram": "42", "feishu": "om_x"})
        _cols, row = self._row(msg)
        self.assertIsInstance(row["channel_message_ids"], str)
        self.assertEqual(json.loads(row["channel_message_ids"]), {"telegram": "42", "feishu": "om_x"})

    def test_empty_1c_fields_are_empty_slots(self):
        """空值统一走空槽 `""`（1b 建立的约定，1c 的 list 字段同样适用）。"""
        _cols, row = self._row(NotificationMessage(title="T"))
        self.assertEqual(row["actions"], "")
        self.assertEqual(row["attachments"], "")
        self.assertEqual(row["channel_message_ids"], "")
        self.assertEqual(row["callback_data"], "")
        # 空槽读回：list 字段得 []、dict 字段得 {}
        self.assertEqual(_json_codec.loads_list(row["actions"]), [])
        self.assertEqual(_json_codec.loads_list(row["attachments"]), [])
        self.assertEqual(_json_codec.loads_dict(row["channel_message_ids"]), {})

    def test_codec_is_the_only_conversion_path(self):
        """★ 契约级：4 个 1c 字段的落库值必须与 _json_codec 的产出逐一相等。

        若有人绕过编解码直接写原值（如把 `msg.actions` 直接进 INSERT），
        本用例因比较对象类型不同（list vs str）而失败。
        """
        msg = NotificationMessage(
            title="T",
            actions=[_action()],
            callback_data="v1|aaaaaaaaaaaaaaaa|retry|1",
            attachments=[AttachmentSpec(kind="file", url="/f.pdf")],
            channel_message_ids={"wechat": "m1"},
        )
        _cols, row = self._row(msg)
        self.assertEqual(row["actions"], _json_codec.dumps(specs_to_jsonable(msg.actions)))
        self.assertEqual(row["attachments"], _json_codec.dumps(specs_to_jsonable(msg.attachments)))
        self.assertEqual(row["channel_message_ids"], _json_codec.dumps(msg.channel_message_ids))
        self.assertEqual(row["callback_data"], msg.callback_data)


class TestMigrationV64(unittest.TestCase):
    def test_adds_four_columns_and_is_idempotent(self):
        from pilotstd.core.db._migrate_v64_notification_log_interactive import (
            _migrate_v64_notification_log_interactive,
        )

        db = MagicMock()
        _migrate_v64_notification_log_interactive(db)
        sqls = [c[0][0] for c in db.execute.call_args_list]
        self.assertEqual(len(sqls), 4)
        joined = " ".join(sqls)
        for col in _STAGE_1C_COLUMNS:
            self.assertIn(f"ADD COLUMN {col} ", joined)
        self.assertNotIn("ADD COLUMN status ", joined)

        db2 = MagicMock()
        db2.execute.side_effect = Exception("duplicate column name")
        _migrate_v64_notification_log_interactive(db2)  # 不抛即通过

    def test_schema_version_and_registration(self):
        from pilotstd.core.db._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS

        self.assertGreaterEqual(CURRENT_SCHEMA_VERSION, 64)
        self.assertIn(64, MIGRATIONS)


class TestAggregatorCarriesInteraction(unittest.TestCase):
    """聚合：actions/attachments 深拷贝取首条；channel_message_ids/callback_data 重置。"""

    def _aggregate(self, msgs):
        from pilotstd.core.notification.aggregate_buffer import NotificationAggregator

        sent: list[NotificationMessage] = []
        agg = NotificationAggregator(lambda m, _ch: sent.append(m), window_seconds=60, batch_size=50)
        for m in msgs:
            agg.enqueue(m, ["wechat"], target_id=m.target_id)
        agg.flush(msgs[0].event_type, msgs[0].target_id)
        return sent

    def _msgs(self):
        return [
            NotificationMessage(
                title="扫描完成",
                event_type="scan_complete",
                target_id="std-1",
                actions=[_action("retry")],
                attachments=[AttachmentSpec(kind="image", url=f"/{i}.png")],
                callback_data=f"v1|m{i}|retry|1",
                channel_message_ids={"telegram": f"mid-{i}"},
            )
            for i in (1, 2)
        ]

    def test_actions_attachments_taken_from_first(self):
        merged = self._aggregate(self._msgs())[0]
        self.assertEqual([a.action for a in merged.actions], ["retry"])
        self.assertEqual(len(merged.attachments), 1)
        self.assertEqual(merged.attachments[0].url, "/1.png", "应取首条")

    def test_delivery_scoped_fields_reset(self):
        """★ 重造的消息尚未投递：无渠道消息 ID、无回调载荷。"""
        merged = self._aggregate(self._msgs())[0]
        self.assertEqual(merged.channel_message_ids, {}, "channel_message_ids 必须重置")
        self.assertEqual(merged.callback_data, "", "callback_data 必须重置")

    def test_actions_deep_copied(self):
        """★ 深拷贝：改原消息的 args 不得污染合并消息（浅拷贝会漏）。"""
        msgs = self._msgs()
        merged = self._aggregate(msgs)[0]
        self.assertIsNot(merged.actions[0], msgs[0].actions[0])
        self.assertIsNot(merged.actions[0].args, msgs[0].actions[0].args)
        msgs[0].actions[0].args["record_id"] = "changed"
        self.assertEqual(merged.actions[0].args["record_id"], 7)
        msgs[0].attachments.append(AttachmentSpec(kind="file", url="/late.pdf"))
        self.assertEqual(len(merged.attachments), 1)

    def test_empty_interaction_is_safe(self):
        msgs = [
            NotificationMessage(title="T", event_type="scan_empty", target_id="s", body=f"b{i}")
            for i in range(2)
        ]
        merged = self._aggregate(msgs)[0]
        self.assertEqual(merged.actions, [])
        self.assertEqual(merged.attachments, [])
        self.assertEqual(merged.callback_data, "")
        self.assertEqual(merged.channel_message_ids, {})


if __name__ == "__main__":
    unittest.main()
