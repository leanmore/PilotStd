# tests/test_notification_stage2a_mapping.py
"""阶段 2a（2026-10-02）：业务事件 → 通知事件的投影（`mapping.py`，纯新增）。

## 本批的判据性质

2a **不接入 `send_event`**，故这里没有"行为变更"判据，只有**表完整性**与**语义**判据：

1. **41 个已注册事件全部有归属**（表驱动，事件清单取自 `events.py::ALL_EVENTS` 本身，
   而不是手抄的 41 个字符串——手抄会在增删事件时静默失效）；
2. **11 个终局事件逐条断言**落在 `task_result` / `task_failure` / `batch_summary`（2026-10-05 S-1 拆分后）；
3. **未知事件回退**：`notify_event=""`（接入方据此走原有行为，**不得抛错**）；
4. **字段值域合法**：`notify_event ∈ NOTIFY_EVENTS`、`content_type ∈ CONTENT_TYPES`、
   `task_kind ∈ TASK_KINDS ∪ {""}`；
5. **不 import `task` 模块**（避免 `notification → task` 依赖环）。

设计文档：docs/plans/notification-redesign/02-目标架构.md §2.1、04-影响面.md §4.1
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.notification.events import ALL_EVENT_KEYS  # noqa: E402
from pilotstd.core.notification.mapping import (  # noqa: E402
    CONTENT_TYPES,
    EVENT_MAPPINGS,
    NOTIFY_EVENTS,
    TASK_KINDS,
    NotificationProjection,
    project,
)

# 用户 2026-10-02 裁决明确点名的 11 个终局事件（**逐条断言**）
_TERMINAL_TO_TASK_RESULT = (
    "download_complete",
    "scan_complete",
)
_TERMINAL_TO_TASK_FAILURE = (
    "download_failed",
    "archive_failed",
    "normalize_failed",
)
_TERMINAL_TO_BATCH_SUMMARY = (
    "archive_complete",
    "normalize_complete",
)


class TestTableCompleteness(unittest.TestCase):
    """表驱动：事件清单取自 `ALL_EVENT_KEYS`（非手抄），故增删事件时自动生效。"""

    def test_all_registered_events_are_mapped(self):
        """★ 41 个已注册事件**全部**有归属，不得落到 notify_event=""。"""
        unmapped = [key for key in ALL_EVENT_KEYS if project(key, {}).notify_event == ""]
        self.assertEqual(unmapped, [], f"以下已注册事件未在 EVENT_MAPPINGS 登记: {unmapped}")

    def test_every_registered_event_lands_in_one_of_seven(self):
        for key in ALL_EVENT_KEYS:
            with self.subTest(event=key):
                self.assertIn(project(key, {}).notify_event, NOTIFY_EVENTS)

    def test_registry_covers_exactly_the_registered_events(self):
        """映射表的键集合必须与事件注册表**双向**一致（多一个孤儿键也算失败）。"""
        self.assertEqual(set(EVENT_MAPPINGS), set(ALL_EVENT_KEYS))
        self.assertEqual(len(EVENT_MAPPINGS), 41, "已注册事件应为 41 个")

    def test_field_value_domains(self):
        for key, m in EVENT_MAPPINGS.items():
            with self.subTest(event=key):
                self.assertIn(m.notify_event, NOTIFY_EVENTS)
                self.assertIn(m.content_type, CONTENT_TYPES)
                self.assertTrue(m.task_kind == "" or m.task_kind in TASK_KINDS)

    def test_projection_returns_dataclass(self):
        p = project("scan_complete", {})
        self.assertIsInstance(p, NotificationProjection)

    def test_per_category_counts_and_sum(self):
        """★ 逐类计数锁定（2026-10-02 教训：报告手算 `batch_summary=12`/`anomaly_alert=8`
        导致"六类合计 43 ≠ 41"的自相矛盾——映射表本身无误，是手算错误）。

        本用例把**权威计数**（由映射表算出）与**期望计数**（与 04-影响面.md §4.1 表一致）
        分别断言，并断言总和 == 已注册事件数。任何"改归属忘了改文档"或"改文档忘了改表"
        都会在此失败。
        """
        import collections

        actual = collections.Counter(m.notify_event for m in EVENT_MAPPINGS.values())
        expected = {
            "task_progress": 1,
            "task_result": 6,
            "task_failure": 5,
            "user_activity": 6,
            "batch_summary": 8,
            "anomaly_alert": 7,
            "security_alert": 5,
            "schedule_reminder": 2,
            "system_health": 1,
            "manual_test": 0,  # 无业务事件承接（仅 POST /api/notification/test 用）
        }
        for name, want in expected.items():
            with self.subTest(notify_event=name):
                self.assertEqual(actual.get(name, 0), want)
        self.assertEqual(sum(actual.values()), len(ALL_EVENT_KEYS))
        self.assertEqual(sum(expected.values()), 41)

    def test_no_event_mapped_to_manual_test(self):
        """`manual_test` 不得承接任何业务事件（它是测试专用类型）。"""
        self.assertEqual([k for k, m in EVENT_MAPPINGS.items() if m.notify_event == "manual_test"], [])


class TestTerminalEvents(unittest.TestCase):
    """11 个终局事件逐条断言（用户裁决点名的清单）。"""

    def test_terminal_result_and_failure_and_summary(self):
        # 2026-10-05 S-1：原 task_lifecycle 已按需求拆为 task_result / task_failure，
        # 且"按批汇总"的终局（archive_complete / normalize_complete）归入 batch_summary。
        for key in _TERMINAL_TO_TASK_RESULT:
            with self.subTest(event=key):
                self.assertEqual(project(key, {}).notify_event, "task_result")
        for key in _TERMINAL_TO_TASK_FAILURE:
            with self.subTest(event=key):
                self.assertEqual(project(key, {}).notify_event, "task_failure")
        for key in _TERMINAL_TO_BATCH_SUMMARY:
            with self.subTest(event=key):
                self.assertEqual(project(key, {}).notify_event, "batch_summary")

    def test_batch_terminal_and_user_activity(self):
        # 既有批量汇总事件保持 batch_summary；收藏放弃汇总改归 user_activity（D-5=A）。
        for key in ("batch_download_complete", "query_empty", "batch_query_summary"):
            with self.subTest(event=key):
                self.assertEqual(project(key, {}).notify_event, "batch_summary")
        with self.subTest(event="favorite_abandoned_summary"):
            self.assertEqual(project("favorite_abandoned_summary", {}).notify_event, "user_activity")

    def test_terminal_lists_are_disjoint(self):
        # 拆分后三组终局互不相交（避免"同一事件被两条口径都认领"）。
        a = set(_TERMINAL_TO_TASK_RESULT)
        b = set(_TERMINAL_TO_TASK_FAILURE)
        c = set(_TERMINAL_TO_BATCH_SUMMARY)
        self.assertEqual(a & b, set())
        self.assertEqual(a & c, set())
        self.assertEqual(b & c, set())
        self.assertEqual(len(a) + len(b) + len(c), 7)

    def test_classification_principle(self):
        """分类原则（2026-10-05 S-1 后）：单条成功终局 → task_result；单条失败终局 → task_failure；
        一次批量运行的总结 → batch_summary。"""
        # 单条成功终局
        for key in ("download_complete", "scan_complete"):
            with self.subTest(event=key):
                self.assertEqual(project(key, {}).notify_event, "task_result")
        # 单条失败终局
        for key in ("download_failed", "archive_failed", "normalize_failed"):
            with self.subTest(event=key):
                self.assertEqual(project(key, {}).notify_event, "task_failure")
        # 批量汇总（含"规范化/存档完成"这两个按批调用的事件）
        for key in ("batch_download_complete", "batch_query_summary", "archive_complete", "normalize_complete"):
            with self.subTest(event=key):
                self.assertEqual(project(key, {}).notify_event, "batch_summary")


class TestFallbackSemantics(unittest.TestCase):
    """未知事件 → `notify_event=""`（回退语义，接入方不得抛错）。"""

    def test_unknown_event_returns_empty(self):
        for unknown in ("not_a_real_event", "", "SCAN_COMPLETE", "scan_complete "):
            with self.subTest(event=unknown):
                p = project(unknown, {})
                self.assertEqual(p.notify_event, "")
                self.assertEqual(p.content_type, "")
                self.assertEqual(p.task_kind, "")
                self.assertEqual(p.correlation_id, "")
                self.assertEqual(p.task_context, {})

    def test_fallback_does_not_raise(self):
        """任何未知 key（含 None 强转的空串）都不得抛异常。"""
        try:
            project("whatever", {"a": 1})
        except Exception as e:  # noqa: BLE001
            self.fail(f"未知事件不得抛异常: {type(e).__name__}: {e}")

    def test_case_sensitive(self):
        """映射大小写敏感（避免"看着像"就误命中）。"""
        self.assertEqual(project("Scan_Complete", {}).notify_event, "")
        self.assertEqual(project("scan_complete", {}).notify_event, "task_result")


class TestDataParameterForFutureBranches(unittest.TestCase):
    """4 个分支归属事件：本批恒返回单值，但 `data` 参数已留门。"""

    BRANCH_EVENTS = (
        "auto_backup",
        "image_update_available",
        "validity_batch_report",
        "validity_round_summary",
    )

    def test_branch_events_return_single_value_regardless_of_data(self):
        """本批不实现分支判定：同一事件传不同 data 仍得同一投影。"""
        for key in self.BRANCH_EVENTS:
            with self.subTest(event=key):
                a = project(key, {"success": True})
                b = project(key, {"success": False, "error": "boom"})
                self.assertEqual(a.notify_event, b.notify_event)
                self.assertNotEqual(a.notify_event, "")

    def test_signature_accepts_data(self):
        """签名必须接受 data（阶段 2a 不用，但避免后续批次改签名波及调用方）。"""
        import inspect

        sig = inspect.signature(project)
        self.assertEqual(list(sig.parameters), ["event_type", "data"])


class TestNoTaskDependency(unittest.TestCase):
    """不 import `task` 模块（避免 notification → task 依赖环）。"""

    def test_mapping_does_not_import_task_module(self):
        import ast
        from pathlib import Path

        src = Path("pilotstd/core/notification/mapping.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
        offenders = [m for m in imported if m.startswith("pilotstd.core.task") or m == "task"]
        self.assertEqual(offenders, [], f"mapping.py 不得 import task 模块: {offenders}")

    def test_task_kinds_are_all_used(self):
        """`TASK_KINDS` 词表不得有孤儿值（每个值至少被一个事件使用）。

        注：`TASK_KINDS` 是**业务域**名词表，与 `_builders_system.py::_TASK_NAME_KEY_MAP`
        的 9 个**定时任务名**不同轴（后者是"哪个 cron 在跑"）——02-目标架构.md §2.3 原文
        称二者"恰好对应"经实测**不成立**，本用例不复制该错误断言，改判"词表自洽"。
        """
        used = {m.task_kind for m in EVENT_MAPPINGS.values() if m.task_kind}
        self.assertEqual(set(TASK_KINDS) - used, set(), "存在未被任何事件使用的 task_kind")

    def test_task_kind_vocabulary_is_distinct_from_scheduled_task_names(self):
        """记录"两套词表不同轴"这一实测事实，防止后人再次误引 02 文档的旧表述。"""
        from pilotstd.core.notification._builders_system import _TASK_NAME_KEY_MAP

        self.assertNotEqual(set(TASK_KINDS), set(_TASK_NAME_KEY_MAP))


if __name__ == "__main__":
    unittest.main()
