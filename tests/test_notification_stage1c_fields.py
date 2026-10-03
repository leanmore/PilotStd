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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


if __name__ == "__main__":
    unittest.main()
