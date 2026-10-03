# tests/test_notification_stage2b_wiring.py
"""阶段 2b-接入（2026-10-02）：把 `project()` 接入 `send_event`，**默认不生效**。

## 本批的判据性质

2b 拆成"接入"与"启用"两步。本批是**接入**：把投影接到 `send_event` 上，但
`NOTIFY_REDESIGN_STAGE` 默认仍为 `1`，故 `is_mapping_enabled()` 为假、系统行为**零变化**。

因此本文件的判据是：

1. **默认（stage=1）下零行为变更**：走真实 `send_event` 的落库值与 1c 时**逐列相等**，
   且 `notify_event`/`content_type`/`task_kind` 三列为空；
2. **stage=2 时投影生效**：同一条事件在 stage=2 下三个字段被回填，**且旧 11 列不变**；
3. **失败不影响主流程**：`project()` 抛异常时通知照发（回退为未映射）；
4. **接入点唯一**：`project(` 在生产代码里只在 `manager._apply_mapping` 出现一处。

设计文档：docs/plans/notification-redesign/06-阶段0-1实施方案.md §3.2
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fixtures.engine_mock_tree import ConfigStub  # noqa: E402

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

# 2b 之前（1c 起）INSERT 的完整列集合——本批 stage=1 下必须逐列相同
_SNAPSHOT_BEFORE_2B = _LEGACY_COLUMNS + _STAGE_1A_COLUMNS + _STAGE_1B_COLUMNS + _STAGE_1C_COLUMNS

_PAYLOAD = {"total": 3, "success": 3, "failed": 0, "failed_files": []}


class _SendEventHarness(unittest.TestCase):
    """公共装置：真实 NotificationManager + 真 builder + 桩 DB，捕获 `notification_log` 的 INSERT。"""

    def _make(self, enabled: bool = True):
        from pilotstd.core.notification.manager import NotificationManager

        cfg = ConfigStub(
            {
                "notification.enabled": enabled,
                "notification.aggregate_enabled": False,  # 关闭聚合 → 直接走 _send_now
                "notification.rules.scan_complete": ["wechat"],
                "notification.delivery_health_enabled": False,
            }
        )
        # NotificationManager 构造时会读 config._filepath 以定位凭证目录（真实 ConfigManager 有此属性）
        cfg._filepath = os.path.join(os.path.dirname(__file__), "test_config.json")
        db = MagicMock()
        db.fetchone.return_value = None
        db.fetchall.return_value = []
        mgr = NotificationManager(cfg, db, 1)
        mgr._enabled = enabled
        mgr._channels = {"wechat": MagicMock(send=MagicMock(return_value=True))}
        return mgr, db

    def _log_insert(self, db):
        """从 db.execute 调用里找出 INSERT INTO notification_log，返回 (列名, 取值)。"""
        for call in db.execute.call_args_list:
            sql = call[0][0]
            if "INSERT INTO notification_log" in sql:
                cols = [c.strip() for c in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
                return cols, dict(zip(cols, call[0][1]))
        self.fail("未捕获到 notification_log 的 INSERT")

    def _send(self, mgr, stage: str | None = None):
        env = {k: v for k, v in os.environ.items() if k != "NOTIFY_REDESIGN_STAGE"}
        if stage is not None:
            env["NOTIFY_REDESIGN_STAGE"] = stage
        with patch.dict(os.environ, env, clear=True):
            mgr.send_event("scan_complete", dict(_PAYLOAD))


class TestDefaultIsZeroChange(_SendEventHarness):
    """判据 1：默认（未设 stage → 1）下，落库值与 1c 时逐列相等。"""

    def test_notification_log_snapshot_unchanged(self):
        mgr, db = self._make()
        self._send(mgr)  # 不设环境变量
        cols, row = self._log_insert(db)
        self.assertEqual(cols, _SNAPSHOT_BEFORE_2B)
        # 旧 11 列逐列断言（沿用 1a/1b/1c 判据；标题取自真实 builder 的产出）
        self.assertEqual(row["event_type"], "scan_complete")
        self.assertEqual(row["channel"], "wechat")
        self.assertEqual(row["title"], "扫描完成，全部识别成功")
        self.assertEqual(row["status"], "success")
        self.assertEqual(row["error_msg"], "")
        self.assertIsNotNone(row["sent_at"])
        self.assertEqual(row["aggregated_count"], 1)
        self.assertIsNone(row["link"])
        self.assertEqual(row["icon"], "pi pi-search")  # scan_complete builder 的图标
        # 1a/1b/1c 的列取值不变
        self.assertEqual(row["delivery_status"], "pending")
        self.assertEqual(row["ack_status"], "none")
        self.assertEqual(row["task_context"], "")
        self.assertEqual(row["actions"], "")
        self.assertEqual(row["callback_data"], "")
        self.assertEqual(row["attachments"], "")
        self.assertEqual(row["channel_message_ids"], "")

    def test_mapping_fields_empty_by_default(self):
        """★ 默认 stage=1 → 三个投影字段必须为空（否则就是行为变更）。"""
        mgr, db = self._make()
        self._send(mgr)
        _cols, row = self._log_insert(db)
        self.assertEqual(row["notify_event"], "")
        self.assertEqual(row["content_type"], "")

    def test_stage_0_and_1_both_disabled(self):
        for stage in ("0", "1"):
            with self.subTest(stage=stage):
                mgr, db = self._make()
                self._send(mgr, stage=stage)
                _cols, row = self._log_insert(db)
                self.assertEqual(row["notify_event"], "")

    def test_identity_fields_untouched(self):
        """`correlation_id` 明确不在本批填充范围（属 2b-启用/2.5）。"""
        mgr, db = self._make()
        self._send(mgr, stage="2")
        _cols, row = self._log_insert(db)
        self.assertEqual(row["correlation_id"], "")
        self.assertEqual(row["task_context"], "")


class TestStageTwoAppliesProjection(_SendEventHarness):
    """判据 2：stage=2 时投影生效，且**旧 11 列不变**（只多出三个字段的值）。"""

    def test_projection_fields_filled(self):
        mgr, db = self._make()
        self._send(mgr, stage="2")
        _cols, row = self._log_insert(db)
        self.assertEqual(row["notify_event"], "task_lifecycle")
        self.assertEqual(row["content_type"], "list")

    def test_legacy_columns_unchanged_under_stage_two(self):
        """★ 启用投影**不得**改变旧列：同一输入分别在 stage=1 与 stage=2 下落库，旧列应相等。"""
        mgr1, db1 = self._make()
        self._send(mgr1, stage="1")
        _c1, row1 = self._log_insert(db1)

        mgr2, db2 = self._make()
        self._send(mgr2, stage="2")
        _c2, row2 = self._log_insert(db2)

        for col in _LEGACY_COLUMNS + _STAGE_1A_COLUMNS + _STAGE_1C_COLUMNS:
            if col == "sent_at":
                continue  # 当前时间戳：两次发送必然不同，不参与逐列比较
            with self.subTest(column=col):
                self.assertEqual(row1[col], row2[col], f"{col} 在启用投影后被改变了")
        # 三列投影字段按预期改变，且都在 1b/2b 的列里
        self.assertEqual(row1["notify_event"], "")
        self.assertEqual(row2["notify_event"], "task_lifecycle")
        self.assertEqual(row1["content_type"], "")
        self.assertEqual(row2["content_type"], "list")

    def test_only_notify_event_content_type_task_kind_change(self):
        """stage=2 相对 stage=1 的差异**只允许**出现在三列投影字段上。"""
        mgr1, db1 = self._make()
        self._send(mgr1, stage="1")
        cols, row1 = self._log_insert(db1)
        mgr2, db2 = self._make()
        self._send(mgr2, stage="2")
        _c, row2 = self._log_insert(db2)

        changed = {c for c in cols if row1[c] != row2[c]}
        # sent_at 是当前时间戳，两次发送必然不同 → 允许；
        # 其余差异**只允许**是 notify_event / content_type 两列
        self.assertEqual(changed - {"sent_at"}, {"notify_event", "content_type"})

    def test_unknown_event_still_sent(self):
        """未知事件 → 投影为空，但通知**照发**（回退语义）。"""
        mgr, db = self._make()
        cfg_rule = "notification.rules.made_up_event"
        mgr._cfg._data[cfg_rule] = ["wechat"]  # type: ignore[attr-defined]
        with patch.dict(os.environ, {"NOTIFY_REDESIGN_STAGE": "2"}, clear=False):
            mgr.send_event("made_up_event", {"a": 1})
        _cols, row = self._log_insert(db)
        self.assertEqual(row["notify_event"], "")
        self.assertEqual(row["event_type"], "made_up_event")


class TestProjectionFailureIsSafe(_SendEventHarness):
    """判据 3：投影失败不影响主流程（旁路增强不得吃掉通知）。"""

    def test_project_exception_does_not_block_notification(self):
        mgr, db = self._make()
        with patch.dict(os.environ, {"NOTIFY_REDESIGN_STAGE": "2"}, clear=False):
            with patch("pilotstd.core.notification._manager_ops.project", side_effect=RuntimeError("boom")):
                with self.assertLogs("pilotstd.core.notification._manager_ops", level="WARNING"):
                    mgr.send_event("scan_complete", dict(_PAYLOAD))
        _cols, row = self._log_insert(db)
        # 通知仍然发出（有人收到）、三个字段按未映射处理
        self.assertEqual(row["event_type"], "scan_complete")
        self.assertEqual(row["notify_event"], "")
        self.assertEqual(row["content_type"], "")
        mgr._channels["wechat"].send.assert_called_once()

    def test_disabled_notification_skips_everything(self):
        """通知总开关关闭时，连投影都不该执行（早退在接入点之前）。"""
        mgr, db = self._make(enabled=False)
        with patch.dict(os.environ, {"NOTIFY_REDESIGN_STAGE": "2"}, clear=False):
            with patch("pilotstd.core.notification._manager_ops.project") as proj:
                mgr.send_event("scan_complete", dict(_PAYLOAD))
        proj.assert_not_called()


class TestWiringBoundaries(unittest.TestCase):
    """判据 4：接入点唯一、改动面受限。"""

    def test_project_called_from_single_place(self):
        """生产代码里 `project(` 只应在 `_manager_ops.apply_mapping` 出现一次（AST 计数）。

        实测背景：接入最初写在 `manager._apply_mapping`，但使 manager.py 有效行达 519
        （超 G-010 的 500 阻断线），故实现迁至 `_manager_ops`（该文件已是既有拆分落点）。
        本用例锁定"接入点唯一"这一性质——无论落在哪个文件。
        """
        import ast

        found: list[tuple[str, int]] = []
        for rel in ("pilotstd/core/notification/manager.py", "pilotstd/core/notification/_manager_ops.py"):
            tree = ast.parse(Path(rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "project":
                    found.append((rel, node.lineno))
        self.assertEqual(len(found), 1, f"project 调用点应唯一，实测 {found}")

    def test_apply_mapping_is_guarded_by_stage(self):
        """`apply_mapping` 首条可执行语句必须是 stage 守卫（否则默认行为就变了）。"""
        src = Path("pilotstd/core/notification/_manager_ops.py").read_text(encoding="utf-8")
        body = src.split("def apply_mapping", 1)[1]
        first_stmt = next(line.strip() for line in body.splitlines()[1:] if line.strip().startswith(("if ", "try")))
        self.assertTrue(first_stmt.startswith("if not is_mapping_enabled()"), first_stmt)

    def test_mapping_module_not_imported_elsewhere(self):
        """除 `_manager_ops.py` 外，生产代码不得 import mapping/stage（避免多处接入）。

        `manager.py` 自身也不再直接 import——实现迁出后它只经 `self.ops` 调用。
        """
        offenders: list[str] = []
        for path in Path("pilotstd").rglob("*.py"):
            if path.name in ("mapping.py", "stage.py", "_manager_ops.py"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "notification.mapping" in text or "from .mapping import" in text:
                offenders.append(str(path))
            if "notification.stage" in text or "from .stage import" in text:
                offenders.append(str(path))
        self.assertEqual(offenders, [], f"mapping/stage 不应被其它生产模块引用: {offenders}")

    def test_message_model_unchanged_in_this_batch(self):
        """★ 本批**不**新增消息字段：`task_kind` 只存在于投影结果，不在 NotificationMessage 上。

        理由：用户裁决的接入范围只列了 notify_event / content_type；给消息加字段
        需同批加迁移/白名单/列，属独立批次。此断言防止"顺手加字段"。
        """
        from pilotstd.core.notification.channel import NotificationMessage

        self.assertFalse(hasattr(NotificationMessage(title="t"), "task_kind"))
        from pilotstd.core.notification.manager import _QUEUE_MESSAGE_FIELDS

        self.assertNotIn("task_kind", _QUEUE_MESSAGE_FIELDS)


if __name__ == "__main__":
    unittest.main()
