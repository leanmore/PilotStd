# tests/test_notification_stage2b_enable_grey.py
"""阶段 2b-启用（2026-10-02）：**灰度采样报告** —— 集成层 + 落库层的可执行形式。

## 为什么做成测试而不是一次性脚本

"真实链路灰度验证"若只跑一次脚本，结论无法回归、无法复现。本文件把它固化为测试：
用**真实 NotificationManager + 真实 builder + 真实 SQLite 库（跑完整迁移链）**，
对**七类通知事件各取 ≥1 条**触发 `send_event`，分别以 `stage=1`（回滚档）与
`stage=2`（默认档）各跑一遍，落库后逐列对照。这样：

- **集成层**：走的是真实 send_event → builder → 投影 → `_send_now` → `notification_log` 全链；
- **落库层**：断言两档的差异**只允许**出现在 `notify_event` / `content_type` 两列；
- **可复现**：任何人 `pytest tests/test_notification_stage2b_enable_grey.py -q` 即可复核。

## 本批不触碰外部环境

不连生产（`192.168.1.18:9028`）、不发网络请求：库是临时 SQLite 文件（跑真实迁移链），
渠道是替身（记录调用而不出网）。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.db import Database  # noqa: E402
from pilotstd.core.notification.manager import NotificationManager  # noqa: E402
from tests.fixtures.engine_mock_tree import ConfigStub  # noqa: E402

# ── 七类通知事件各取 ≥1 条（载荷键取自对应 builder 的 data.get 集合）──────────────
# 事件 key → (期望 notify_event, 期望 content_type, 载荷)
SAMPLES: dict[str, tuple[str, str, dict]] = {
    "scan_complete": ("task_lifecycle", "list", {"total": 3, "success": 3, "failed": 0, "failed_files": []}),
    "announcement_check_complete": (
        "batch_summary",
        "list",
        {
            "source": "gb",
            "total_announcements": 5,
            "gb_count": 3,
            "hb_count": 1,
            "db_count": 1,
            "total_standards": 9,
            "failures": 0,
        },
    ),
    "task_execution_failed": ("anomaly_alert", "text", {"task_name": "auto_scan", "error": "boom"}),
    "security_token_refreshed": (
        "security_alert",
        "text",
        {"rotated_at": "2026-10-02T10:00:00", "from_ip": "127.0.0.1", "db_synced": True},
    ),
    "date_reminder": (
        "schedule_reminder",
        "field_list",
        {
            "user_id": 1,
            "record_id": 1,
            "standard_number": "GB/T 1-2024",
            "std_name": "测试标准",
            "days_before": 7,
            "remind_type": "expire",
        },
    ),
    "notification_delivery_failed": (
        "system_health",
        "text",
        {"channel": "wechat", "reason": "consecutive", "samples": 10, "failures": 10, "consecutive": 5},
    ),
}

# 通知事件 → 该类的代表业务事件（覆盖性断言用）
_CATEGORY_REPRESENTATIVE = {
    "task_lifecycle": "scan_complete",
    "batch_summary": "announcement_check_complete",
    "anomaly_alert": "task_execution_failed",
    "security_alert": "security_token_refreshed",
    "schedule_reminder": "date_reminder",
    "system_health": "notification_delivery_failed",
}

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
_NEW_12_COLUMNS = [
    "message_id",
    "correlation_id",
    "delivery_status",
    "ack_status",
    "task_id",
    "notify_event",
    "content_type",
    "task_context",
    "actions",
    "callback_data",
    "attachments",
    "channel_message_ids",
]
# 本批允许出现差异的列（其余列必须逐列相等）
_ALLOWED_DIFF = {"notify_event", "content_type"}


class GreySamplingReport(unittest.TestCase):
    """灰度采样：真实库 + 真实 builder，stage=1 与 stage=2 两档对照。"""

    def setUp(self):
        # **每个用例一次采样用全新库**：否则同一库里的历史行会污染本次采样
        # （setdefault 取到上一档的行→假失败）。
        self._dirs: list[str] = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _new_db(self) -> tuple[Database, str]:
        d = tempfile.mkdtemp(prefix="grey_2b_")
        self._dirs.append(d)
        path = str(Path(d) / "grey.db")
        db = Database(path)  # 跑真实迁移链
        return db, d

    # ── 采样装置 ───────────────────────────────────────────────────────────
    def _run_stage(self, stage: str) -> dict[str, dict]:
        """以给定 stage 跑全部样本（**全新库**），返回 {event_type: 落库行}。"""
        db, d = self._new_db()
        cfg = ConfigStub(
            {
                "notification.enabled": True,
                "notification.aggregate_enabled": False,  # 关闭聚合 → 每条直发，便于逐条比对
                "notification.delivery_health_enabled": False,
                **{f"notification.rules.{ev}": ["wechat"] for ev in SAMPLES},
            }
        )
        cfg._filepath = str(Path(d) / "cfg.json")
        mgr = NotificationManager(cfg, db, 1)
        mgr._enabled = True
        calls: list[str] = []
        mgr._channels = {"wechat": MagicMock(send=lambda msg: (calls.append(msg.title), True)[1])}

        # 冻结时钟：让两档的 sent_at 完全一致，从而**全部 11 个旧列**都可逐列比较。
        # 用 datetime 的**子类**做桩（比 MagicMock 安全：now() 返回真实 datetime，isoformat 自然可用）
        frozen = datetime(2026, 10, 2, 10, 0, 0)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):  # noqa: ANN001, ARG003
                return frozen

        with patch.dict(os.environ, {"NOTIFY_REDESIGN_STAGE": stage}, clear=False):
            with patch("pilotstd.core.notification.manager.datetime", _FrozenDatetime):
                for ev, (_ne, _ct, payload) in SAMPLES.items():
                    mgr.send_event(ev, dict(payload))
        self.channel_calls = calls

        rows: dict[str, dict] = {}
        for r in db.fetchall("SELECT * FROM notification_log ORDER BY id"):
            row = dict(r)
            rows.setdefault(row["event_type"], row)
        cols = {r[1] for r in db._get_conn().execute("PRAGMA table_info(notification_log)")}
        db.close()
        self.schema_columns = cols
        return rows

    # ── 报告：采样明细 ─────────────────────────────────────────────────────
    def test_report_sampling_detail(self):
        """★ 输出采样明细（`-s` 可见）：每条样本的 event_type / notify_event / content_type。"""
        stage1 = self._run_stage("1")
        stage2 = self._run_stage("2")
        lines = ["", "阶段 2b 灰度采样明细（真实库 + 真实 builder）", "-" * 78]
        lines.append(f"{'事件':<32}{'期望类别':<18}{'stage=1':<12}{'stage=2':<18}{'content_type'}")
        for ev, (ne, ct, _p) in SAMPLES.items():
            r1, r2 = stage1.get(ev, {}), stage2.get(ev, {})
            col1 = r1.get("notify_event", "<缺失>")
            col2 = r2.get("notify_event", "<缺失>")
            lines.append(f"{ev:<32}{ne:<18}{col1:<12}{col2:<18}{r2.get('content_type', '')}")
        lines.append("-" * 78)
        lines.append(f"样本数：{len(SAMPLES)} ｜ 七类覆盖：{len({ne for ne, _ct, _p in SAMPLES.values()})}/7")
        lines.append(f"stage=1 落库条数：{len(stage1)} ｜ stage=2 落库条数：{len(stage2)}")
        print("\n".join(lines))

        # 采样本身必须完整：每条样本都落库（否则报告缺行）
        self.assertEqual(set(stage1), set(SAMPLES))
        self.assertEqual(set(stage2), set(SAMPLES))

    # ── 落库层：判据 ───────────────────────────────────────────────────────
    def test_seven_categories_covered(self):
        """★ 集成层：七类中**六类**有真实业务事件承接（`manual_test` 无业务事件，设计如此）。"""
        from pilotstd.core.notification.mapping import EVENT_MAPPINGS

        stage2 = self._run_stage("2")
        actual = {row["notify_event"] for row in stage2.values()}
        self.assertEqual(actual, set(_CATEGORY_REPRESENTATIVE))
        self.assertEqual(len(actual), 6)
        # 第七类 manual_test 在本仓无业务事件承接——由映射表层证明
        self.assertEqual([k for k, m in EVENT_MAPPINGS.items() if m.notify_event == "manual_test"], [])

    def test_stage_one_leaves_projection_columns_empty(self):
        """★ 回滚档：`notify_event` / `content_type` 全为空（= 改造前语义）。"""
        stage1 = self._run_stage("1")
        for ev, row in stage1.items():
            with self.subTest(event=ev):
                self.assertEqual(row["notify_event"], "")
                self.assertEqual(row["content_type"], "")

    def test_stage_two_fills_expected_values(self):
        """★ 默认档：每条样本的 `notify_event`/`content_type` 与映射表预期**逐条相等**。"""
        stage2 = self._run_stage("2")
        for ev, (ne, ct, _p) in SAMPLES.items():
            with self.subTest(event=ev):
                self.assertEqual(stage2[ev]["notify_event"], ne)
                self.assertEqual(stage2[ev]["content_type"], ct)
                self.assertNotEqual(stage2[ev]["notify_event"], "")

    def test_diff_limited_to_two_columns(self):
        """★ 落库层核心判据：两档差异**只允许**出现在 notify_event / content_type。"""
        stage1 = self._run_stage("1")
        stage2 = self._run_stage("2")
        for ev in SAMPLES:
            r1, r2 = stage1[ev], stage2[ev]
            with self.subTest(event=ev):
                differing = {c for c in r1 if r1[c] != r2[c]}
                self.assertTrue(
                    differing <= _ALLOWED_DIFF,
                    f"{ev}: 出现允许范围外的列差异 {sorted(differing - _ALLOWED_DIFF)}",
                )
                # 至少 notify_event 有变化（否则说明投影没生效）
                self.assertIn("notify_event", differing)

    def test_legacy_eleven_columns_identical(self):
        """★ 旧 11 列（含 sent_at，已冻结时钟）在 stage=1 与 stage=2 下逐列相等。"""
        stage1 = self._run_stage("1")
        stage2 = self._run_stage("2")
        for ev in SAMPLES:
            for col in _LEGACY_COLUMNS:
                with self.subTest(event=ev, column=col):
                    self.assertEqual(stage1[ev][col], stage2[ev][col])

    def test_new_columns_other_than_projection_identical(self):
        """1a/1b/1c 的其余 10 列（除 notify_event/content_type）也必须逐列相等。"""
        stage1 = self._run_stage("1")
        stage2 = self._run_stage("2")
        others = [c for c in _NEW_12_COLUMNS if c not in _ALLOWED_DIFF]
        for ev in SAMPLES:
            for col in others:
                with self.subTest(event=ev, column=col):
                    self.assertEqual(stage1[ev][col], stage2[ev][col])

    def test_delivery_result_unchanged(self):
        """★ 渠道投递结果不变：两档下每条样本都投递成功（`status='success'`）且各调用一次。"""
        stage1 = self._run_stage("1")
        calls1 = list(self.channel_calls)
        stage2 = self._run_stage("2")
        calls2 = list(self.channel_calls)

        for stage_rows in (stage1, stage2):
            for ev, row in stage_rows.items():
                with self.subTest(event=ev):
                    self.assertEqual(row["status"], "success")
        self.assertEqual(calls1, calls2, "渠道调用序列（标题）在两档间不一致")

    def test_schema_has_all_columns_but_not_task_kind(self):
        """落库层：真实库的 `notification_log` 有 25 列（含 4 个非标量），且**无** task_kind。"""
        self._run_stage("2")  # 采样会记录本次库的列集
        self.assertEqual(len(self.schema_columns), 25)
        for col in ("message_id", "task_context", "actions", "channel_message_ids", "content_type"):
            self.assertIn(col, self.schema_columns)
        self.assertNotIn("task_kind", self.schema_columns, "task_kind 提前落库了（消费点应为阶段 2.5）")

    def test_channel_send_count_is_one_per_sample_per_stage(self):
        """聚合关闭 → 每条样本每档被投递 1 次（无重复投递；两档投递**次数**一致）。"""
        self._run_stage("1")
        n1 = len(self.channel_calls)
        self._run_stage("2")
        n2 = len(self.channel_calls)
        self.assertEqual(n1, len(SAMPLES), "stage=1：每条样本应恰好投递 1 次")
        self.assertEqual(n2, len(SAMPLES), "stage=2：每条样本应恰好投递 1 次（次数不因投影而变）")


if __name__ == "__main__":
    unittest.main()
