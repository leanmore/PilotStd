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
# 阶段 2.5a：INSERT 再增 task_kind 一列（标量，非 JSON）
# v67（2026-10-05 通知聚合 B1）：再增 failed_items 一列（TEXT 存 JSON，批量导入失败明细）
_SNAPSHOT_AFTER_2_5A = _SNAPSHOT_BEFORE_2B + ["task_kind", "failed_items"]

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


class TestZeroChangeBaseline(_SendEventHarness):
    """判据 1：**回滚档**（`NOTIFY_REDESIGN_STAGE=1`）下，落库值与 1c 时逐列相等。

    本批（2b-启用）把默认值提为 2，故"零变化"基线改为**显式** stage=1 断言
    ——它同时就是"一键回滚"的验证：回滚不需要动代码。
    """

    def test_notification_log_snapshot_unchanged(self):
        mgr, db = self._make()
        self._send(mgr, stage="1")
        cols, row = self._log_insert(db)
        self.assertEqual(cols, _SNAPSHOT_AFTER_2_5A)
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

    def test_mapping_fields_empty_under_rollback_stage(self):
        """★ 回滚档（stage=1）→ 两个投影字段必须为空（即回到改造前语义）。"""
        mgr, db = self._make()
        self._send(mgr, stage="1")
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
        """`correlation_id` / `task_context` 明确不在本阶段填充范围（属 2.5）。"""
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
        self.assertEqual(row["notify_event"], "task_result")
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
        self.assertEqual(row2["notify_event"], "task_result")
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
        # 其余差异**只允许**是三个投影列（2.5a 起 task_kind 也随 stage 变化）
        self.assertEqual(changed - {"sent_at"}, {"notify_event", "content_type", "task_kind"})

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


class TestDefaultStageEnablesMapping(_SendEventHarness):
    """判据 1b：2b-启用后**默认档**（未设环境变量 → 2）应回填两个字段。

    这是本批的**行为变更点**：默认值由 1 提到 2，故不设环境变量时映射即生效。
    """

    def test_default_fills_projection_fields(self):
        mgr, db = self._make()
        self._send(mgr)  # 不设环境变量 → 默认 2
        _cols, row = self._log_insert(db)
        self.assertEqual(row["notify_event"], "task_result")
        self.assertEqual(row["content_type"], "list")

    def test_default_still_keeps_legacy_columns(self):
        """默认档下旧 11 列仍须为既有取值（启用映射不该改动旧列）。"""
        mgr, db = self._make()
        self._send(mgr)
        _cols, row = self._log_insert(db)
        self.assertEqual(row["event_type"], "scan_complete")
        self.assertEqual(row["title"], "扫描完成，全部识别成功")
        self.assertEqual(row["status"], "success")
        self.assertEqual(row["aggregated_count"], 1)

    def test_rollback_by_env_restores_zero_change(self):
        """★ 一键回滚验证：设 stage=1 → 投影字段回空（不改一行代码）。"""
        mgr, db = self._make()
        self._send(mgr, stage="1")
        _cols, row = self._log_insert(db)
        self.assertEqual(row["notify_event"], "")
        self.assertEqual(row["content_type"], "")


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

    def test_task_kind_now_a_message_field(self):
        """★ 阶段 2.5a 起 `task_kind` **是**消息字段并在队列白名单内（2b 期间相反）。"""
        from pilotstd.core.notification.channel import NotificationMessage
        from pilotstd.core.notification.manager import _QUEUE_MESSAGE_FIELDS

        self.assertTrue(hasattr(NotificationMessage(title="t"), "task_kind"))
        self.assertIn("task_kind", _QUEUE_MESSAGE_FIELDS)


class TestTaskKindPersisted(unittest.TestCase):
    """`task_kind` **已落地**（阶段 2.5a 翻转闸门后的"必须落库"断言）。

    演化：2a/2b 期间本类是 `TestTaskKindAntiCorrosion`（锁"不得落库"），
    2.5a 按裁决**逐条翻转**为"必须落库"——闸门按设计主动拦下了 2.5a 的实现，
    这正是闸门有效的证明（见提交信息与交付报告的判别力留痕）。
    """

    def test_persisted_to_notification_log(self):
        """★ `task_kind` 必须出现在 notification_log 的 INSERT 列里。"""
        from pathlib import Path

        src = Path("pilotstd/core/notification/_manager_ops.py").read_text(encoding="utf-8")
        insert = src.split("INSERT INTO notification_log", 1)[1].split("VALUES", 1)[0]
        self.assertIn("task_kind", insert)

    def test_in_queue_whitelist(self):
        """★ 必须进 `_QUEUE_MESSAGE_FIELDS`——否则静音补发会静默丢失（1a/1b/1c 同类缺陷）。"""
        from pilotstd.core.notification.manager import _QUEUE_MESSAGE_FIELDS

        self.assertIn("task_kind", _QUEUE_MESSAGE_FIELDS)

    def test_is_a_message_field(self):
        """★ `NotificationMessage` 必须有 `task_kind` 字段，默认空串（未设置语义）。"""
        from pilotstd.core.notification.channel import NotificationMessage

        self.assertTrue(hasattr(NotificationMessage(title="t"), "task_kind"))
        self.assertEqual(NotificationMessage(title="t").task_kind, "")

    def test_is_a_table_column(self):
        """★ 真实迁移链产出的 schema 里必须有 task_kind 列（TEXT）。"""
        import shutil
        import tempfile
        from pathlib import Path

        from pilotstd.core.db import Database

        d = tempfile.mkdtemp(prefix="tk_persist_")
        try:
            db = Database(str(Path(d) / "p.db"))
            cols = {r[1]: r[2] for r in db._get_conn().execute("PRAGMA table_info(notification_log)")}
            db.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertIn("task_kind", cols)
        self.assertEqual(cols["task_kind"], "TEXT")

    def test_consume_point_documented_in_sources(self):
        """文档侧防护：`mapping.py` 与 `03-实施路径.md` 均写明**双 SSOT** 与单向翻译约定。"""
        from pathlib import Path

        mapping_src = Path("pilotstd/core/notification/mapping.py").read_text(encoding="utf-8")
        self.assertIn("双 SSOT", mapping_src)
        self.assertIn("只做单向", mapping_src)
        self.assertIn("不提供反向函数", mapping_src)
        self.assertIn("TASK_KIND_TO_TASK_TYPE", mapping_src)

        plan_src = Path("docs/plans/notification-redesign/03-实施路径.md").read_text(encoding="utf-8")
        self.assertIn("阶段 2.5 必做项", plan_src)
        self.assertIn("双 SSOT", plan_src)


class TestTaskKindMappingTable(unittest.TestCase):
    """单向映射表 `task_kind → task_type`（双 SSOT 翻译，**无反向**）。"""

    def test_covers_all_task_kinds(self):
        """九值 `TASK_KINDS` 全部有对应（无遗漏）。"""
        from pilotstd.core.notification.mapping import TASK_KIND_TO_TASK_TYPE, TASK_KINDS

        self.assertEqual(set(TASK_KINDS), set(TASK_KIND_TO_TASK_TYPE))

    def test_targets_are_valid_task_types(self):
        """映射目标必须落在 `TaskType` 值域内（不得发明不存在的队列类型）。"""
        from pilotstd.core.notification.mapping import TASK_KIND_TO_TASK_TYPE
        from pilotstd.task.models import TaskType

        valid = {t.value for t in TaskType}
        self.assertTrue(set(TASK_KIND_TO_TASK_TYPE.values()) <= valid)

    def test_same_name_pairs_are_identity(self):
        """三个同名同义项必须自映射（否则是笔误）。"""
        from pilotstd.core.notification.mapping import TASK_KIND_TO_TASK_TYPE

        for k in ("scan", "query", "organize"):
            with self.subTest(task_kind=k):
                self.assertEqual(TASK_KIND_TO_TASK_TYPE[k], k)

    def test_known_gap_is_documented(self):
        """已知缺口：`TaskType.expire` 无 task_kind 对应（无"到期处理"类通知语义）。

        本用例把它**显式记录**而非默默忽略——一旦将来补上，本用例会失败并提醒更新文档。
        """
        from pilotstd.core.notification.mapping import TASK_KIND_TO_TASK_TYPE
        from pilotstd.task.models import TaskType

        unmapped = {t.value for t in TaskType} - set(TASK_KIND_TO_TASK_TYPE.values())
        self.assertEqual(unmapped, {"expire"})

    def test_no_reverse_function(self):
        """★ **不得提供反向函数**（一对多必然要猜，属后门）。"""
        from pilotstd.core.notification import mapping

        reverse_names = [n for n in dir(mapping) if "task_type_to" in n.lower()]
        self.assertEqual(reverse_names, [], f"出现反向翻译函数: {reverse_names}")

    def test_unknown_returns_empty(self):
        """未知 task_kind（含空串）→ `""`（回退语义，与 `project()` 同口径）。"""
        from pilotstd.core.notification.mapping import task_kind_to_task_type

        self.assertEqual(task_kind_to_task_type("nope"), "")
        self.assertEqual(task_kind_to_task_type(""), "")


if __name__ == "__main__":
    unittest.main()
