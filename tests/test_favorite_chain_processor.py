# tests/test_favorite_chain_processor.py — 收藏下载链处理器测试
# 覆盖：下载阶段（成功/失败/重试上限/批处理上限/user_id 隔离/冷却期/倒序框架）
# 贴合现有链路：pending/failed → download_to_inbox（内部 downloading→archiving→done/failed）

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


@pytest.fixture(scope="module", autouse=True)
def _isolate_env_favorite_chain():
    """模块级 env 隔离：强制注入 SUPERUSER=testadmin，teardown 恢复原值。

    TD-10 P1：替代守卫式 os.environ["SUPERUSER"] 注入（原模式永不恢复，
    会污染后导入的 test_docker_auth 等模块导致登录 401）。
    """
    old_values = {}
    env_vars = {"SUPERUSER": "testadmin"}
    for k, v in env_vars.items():
        old_values[k] = os.environ.get(k)
        os.environ[k] = v
    yield
    for k, old in old_values.items():
        if old is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = old


class TestFavoriteChainProcessor(unittest.TestCase):
    """状态机处理器：使用真实 Database + mock download_to_inbox。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="pilotstd_fc_")
        self.db_path = os.path.join(self.tmpdir, "test.db")
        from pilotstd.core.db import Database
        self.db = Database(self.db_path)  # 迁移链含 v54（favorite_downloads 有 user_id 列）
        self.db.close()  # 处理器/测试各自实例化 Database

        import sqlite3
        self.raw = sqlite3.connect(self.db_path)
        self.raw.execute("PRAGMA busy_timeout=5000")

        # 环境变量：冷却期 0 天（测试默认不过期）
        self._env = patch.dict(os.environ, {"ARCHIVE_COOLDOWN_DAYS": "0"})
        self._env.start()

        # patch 处理器内的 get_db_path
        import pilotstd.services.favorite_chain_processor as fcp
        self._path_patch = patch.object(fcp, "get_db_path", return_value=self.db_path)
        self._path_patch.start()
        self.fcp = fcp

        self._dl_patch = patch(
            "pilotstd.tasks.favorite_download.download_to_inbox",
            side_effect=self._fake_download,
        )
        self._dl_patch.start()

    def tearDown(self):
        self._dl_patch.stop()
        self._path_patch.stop()
        self._env.stop()
        self.raw.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── 工具 ─────────────────────────────────────────────────

    def _seed_announcement(self, record_id: int, std_no: str, publish_date: str | None) -> None:
        self.raw.execute(
            "INSERT INTO announcement_record"
            " (id, source_site, pid, announce_no, standard_number, std_name, publish_date, fetched_at)"
            " VALUES (?, 'ahbz', ?, 'A-1', ?, '标准', ?, '2026-06-01')",
            (record_id, f"p{record_id}", std_no, publish_date),
        )
        self.raw.commit()

    def _seed_favorite(self, user_id: int, record_id: int, status: str = "pending",
                       retry_count: int = 0, publish_date: str | None = "2026-01-01",
                       standard_type: str = "NationalStd") -> int:
        self.raw.execute(
            "INSERT INTO user_favorites (user_id, record_id, status, created_at, updated_at)"
            " VALUES (?, ?, 'pending', datetime('now'), datetime('now'))", (user_id, record_id)
        )
        fav_id = self.raw.execute(
            "SELECT id FROM user_favorites WHERE user_id=? AND record_id=?", (user_id, record_id)
        ).fetchone()[0]
        std_no = self.raw.execute(
            "SELECT standard_number FROM announcement_record WHERE id=?", (record_id,)
        ).fetchone()[0]
        self.raw.execute(
            "INSERT INTO favorite_downloads"
            " (favorite_id, user_id, record_id, status, standard_no,"
            "  standard_name, standard_type, retry_count, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, '标准', ?, ?, datetime('now'), datetime('now'))",
            (fav_id, user_id, record_id, status, std_no, standard_type, retry_count),
        )
        self.raw.commit()
        return fav_id

    def _fake_download(self, favorite_id: int, user_id: int, record_id: int, notify: bool = True) -> None:
        """模拟 download_to_inbox：按 self._dl_mode 置状态（成功 done / 失败 failed / 跳过 skip）。

        notify 参数与真实签名对齐（批量路径传 False 抑制逐条通知）。
        """
        mode = getattr(self, "_dl_mode", "success")
        if mode == "skip":
            from pilotstd.tasks.favorite_download import FavoriteSkip

            raise FavoriteSkip("采标标准，版权受限，自动跳过: 测试标准")
        status = "done" if mode == "success" else "failed"
        err = None if mode == "success" else "模拟下载失败"
        if status == "done":
            self.raw.execute(
                "UPDATE favorite_downloads SET status='done', local_path='/tmp/a.pdf' WHERE favorite_id=?",
                (favorite_id,),
            )
        else:
            self.raw.execute(
                "UPDATE favorite_downloads SET status='failed', error_message=? WHERE favorite_id=?",
                (err, favorite_id),
            )
        self.raw.commit()

    def _fd_status(self, user_id: int, record_id: int) -> tuple:
        return self.raw.execute(
            "SELECT status, retry_count, error_message FROM favorite_downloads"
            " WHERE user_id=? AND record_id=?",
            (user_id, record_id),
        ).fetchone()

    # ── 用例 ─────────────────────────────────────────────────

    def test_download_phase_success(self):
        """3 条 pending（过冷却期）→ 全部 done。"""
        for i in range(1, 4):
            self._seed_announcement(i, f"GB/T {1000+i}", "2026-01-01")
            self._seed_favorite(1, i)
        self._dl_mode = "success"
        stats = self.fcp.process_chain()
        self.assertEqual(stats["download"], 3)
        for i in range(1, 4):
            status, retry, _ = self._fd_status(1, i)
            self.assertEqual(status, "done")

    def test_download_failure_retry_and_abandon(self):
        """失败 → retry_count 递增；达 MAX_RETRIES 次后 abandoned，不再处理。"""
        self._seed_announcement(1, "GB/T 1001", "2026-01-01")
        self._seed_favorite(1, 1)
        self._dl_mode = "fail"

        # MAX_RETRIES 次 cron：逐次递增 → abandoned（每天 04:00 一次 → 7 天兜底窗口）
        for _ in range(self.fcp.MAX_RETRIES):
            self.fcp.process_chain()
        status, retry, _ = self._fd_status(1, 1)
        self.assertEqual(retry, self.fcp.MAX_RETRIES)
        self.assertEqual(status, "abandoned")

        # 再来一次 cron：abandoned 不再处理（retry 不再增长）
        self.fcp.process_chain()
        status, retry, _ = self._fd_status(1, 1)
        self.assertEqual(retry, self.fcp.MAX_RETRIES)
        self.assertEqual(status, "abandoned")

    def test_retry_limit_is_seven_day_window(self):
        """重试上限锁定 7：cron 每天 04:00 触发一次 → 7 天兜底窗口（ADR-007 决策值）。"""
        self.assertEqual(self.fcp.MAX_RETRIES, 7)

    def test_no_artificial_daily_cap(self):
        """A 方案：取消"每天 10 条"人为上限，一轮处理全部到期记录。"""
        for i in range(1, 26):
            self._seed_announcement(i, f"GB/T {2000+i}", "2026-01-01")
            self._seed_favorite(1, i)
        self._dl_mode = "success"

        stats = self.fcp.process_chain()

        self.assertEqual(stats["download"], 25, "不应再受 10 条/天限制")
        self.assertTrue(all(self._fd_status(1, i)[0] == "done" for i in range(1, 26)))

    def test_all_due_records_handed_to_engine_pacing(self):
        """传入下载引擎时，全部到期记录交给引擎节奏（分批/并发/批间冷却）。"""
        for i in range(1, 6):
            self._seed_announcement(i, f"GB/T {3000+i}", "2026-01-01")
            self._seed_favorite(1, i)
        self._dl_mode = "success"

        handled: list[int] = []

        class _FakeEngine:
            def run_paced_batches(self, items, worker):
                handled.extend(items)
                return [worker(it) for it in items]

        processed = self.fcp.process_pending_downloads(_FakeEngine())

        self.assertEqual(len(handled), 5, "5 条到期记录应全部交给引擎")
        self.assertEqual(processed, 5)
        self.assertTrue(all(self._fd_status(1, i)[0] == "done" for i in range(1, 6)))

    def test_no_engine_falls_back_to_sequential(self):
        """未传引擎（旧调用方）时退化为顺序处理，功能不受影响。"""
        self._seed_announcement(1, "GB/T 4001-2020", "2026-01-01")
        self._seed_favorite(1, 1)
        self._dl_mode = "success"

        processed = self.fcp.process_pending_downloads()

        self.assertEqual(processed, 1)
        self.assertEqual(self._fd_status(1, 1)[0], "done")

    def test_user_id_isolation(self):
        """两用户收藏同一 record_id → 状态互不影响。"""
        self._seed_announcement(1, "GB/T 1001", "2026-01-01")
        self._seed_favorite(1, 1)
        self._seed_favorite(2, 1)
        self._dl_mode = "success"
        self.fcp.process_chain()
        s1 = self._fd_status(1, 1)
        s2 = self._fd_status(2, 1)
        self.assertEqual(s1[0], "done")
        self.assertEqual(s2[0], "done")

    def test_cooldown_respected(self):
        """冷却期（28 天）：已过冷却期处理；冷却期内 / 无发布日期的跳过。

        A-1 语义：publish_date 为 NULL/'' 时按 CURRENT_DATE（今日）计，冷却期内
        不处理（不再绕过冷却期）。模块常量 COOLDOWN_DAYS 在导入时冻结
        （favorite_chain_processor.py:28），此处显式 patch.object 覆盖，
        使测试与导入顺序无关（修复全量运行时导入时机不同导致的 flaky）。
        """
        past = (date.today() - timedelta(days=40)).isoformat()
        future = (date.today() + timedelta(days=30)).isoformat()
        with patch.object(self.fcp, "COOLDOWN_DAYS", 28), patch.dict(
            os.environ, {"ARCHIVE_COOLDOWN_DAYS": "28"}
        ):
            self._seed_announcement(1, "GB/T 1001", past)  # 已过冷却期 → 处理
            self._seed_announcement(2, "GB/T 1002", future)  # 未来 → 冷却期内跳过
            self._seed_announcement(3, "GB/T 1003", None)  # 无发布日 → 按今日计 → 跳过
            self._seed_favorite(1, 1)
            self._seed_favorite(1, 2)
            self._seed_favorite(1, 3)
            self._dl_mode = "success"
            stats = self.fcp.process_chain()
            self.assertEqual(stats["download"], 1)

    def test_chain_reverse_order_stats(self):
        """倒序框架：process_chain 返回阶段统计（当前单阶段：download）。"""
        self._seed_announcement(1, "GB/T 1001", "2026-01-01")
        self._seed_favorite(1, 1)
        self._dl_mode = "success"
        stats = self.fcp.process_chain()
        self.assertIn("download", stats)
        self.assertEqual(stats["download"], 1)

    def test_category_gate_excludes_non_national(self):
        """A 修复：行标不进下载阶段，也不消耗重试次数。"""
        self._seed_announcement(1, "HB 1-2020", "2026-01-01")
        self._seed_favorite(1, 1, standard_type="IndustryStd")
        self._seed_announcement(2, "GB/T 1-2020", "2026-01-01")
        self._seed_favorite(1, 2, standard_type="NationalStd")

        self._dl_mode = "success"
        processed = self.fcp.process_pending_downloads()

        self.assertEqual(processed, 1, "只有国标应被处理")
        self.assertEqual(self._fd_status(1, 1)[0], "pending", "行标保持 pending 且不消耗重试")
        self.assertEqual(self._fd_status(1, 2)[0], "done")

    def test_abandon_emits_archive_abandoned_once(self):
        """① 修复：重试耗尽转 abandoned 时必须通知，且只通知一次（原先完全静默）。

        历史缺陷：archive_abandoned 的唯一发送方是已无调度方的 archive_retry_service，
        活跃链放弃时只写日志 → 生产 28 条 abandoned 对应 0 条通知。
        """
        self._seed_announcement(1, "GB/T 1001-2020", "2026-01-01")
        self._seed_favorite(1, 1, retry_count=self.fcp.MAX_RETRIES - 1)
        self._dl_mode = "failed"

        with patch("pilotstd.manager.facade.StandardManager") as mock_mgr:
            self.fcp.process_pending_downloads()

        row = self._fd_status(1, 1)
        self.assertEqual(row[0], "abandoned")
        notifier = mock_mgr.return_value.notification_mgr
        notifier.send_event.assert_called_once()
        event, payload = notifier.send_event.call_args[0]
        self.assertEqual(event, "archive_abandoned")
        self.assertEqual(payload["user_id"], 1)
        self.assertEqual(payload["record_id"], 1)
        self.assertIn("GB/T 1001-2020", payload["standard_info"])
        self.assertEqual(payload["error"], "模拟下载失败")

    def test_skip_mode_marks_terminal_without_retries(self):
        """业务终态跳过（P1，2026-09-21）：一次即 abandoned，不耗尽 7 次重试。

        历史缺陷：采标标准（版权受限）按普通失败处理 → 每条空转 7 天重试窗口、
        逐日发失败通知，最后才放弃（实测 6 条 × 7 天）。
        通知：批量路径（process_chain）按批汇总，本次运行只有 1 条 batch_download_complete。
        """
        self._seed_announcement(1, "GB/T 1066-2020", "2026-01-01")
        self._seed_favorite(1, 1, retry_count=0)
        self._dl_mode = "skip"

        with patch("pilotstd.manager.facade.StandardManager") as mock_mgr:
            self.fcp.process_chain()

        status, retry, err = self._fd_status(1, 1)
        self.assertEqual(status, "abandoned", "业务终态应直接 abandoned")
        self.assertEqual(retry, self.fcp.MAX_RETRIES, "retry_count 拉到上限，确保不再入选")
        self.assertIn("采标标准", err or "")

        notifier = mock_mgr.return_value.notification_mgr
        self.assertEqual(notifier.send_event.call_count, 1, "批量路径只发 1 条汇总，不逐条刷屏")
        event, payload = notifier.send_event.call_args[0]
        self.assertEqual(event, "batch_download_complete")
        self.assertEqual(payload["skipped"], 1)
        self.assertEqual(payload["failed"], 0)

        # 再跑一轮：abandoned 不在扫描范围 → 不再通知、状态不变
        with patch("pilotstd.manager.facade.StandardManager") as mock_mgr2:
            self.fcp.process_chain()
        mock_mgr2.return_value.notification_mgr.send_event.assert_not_called()
        self.assertEqual(self._fd_status(1, 1)[0], "abandoned")

    def test_run_summary_counts_mixed_outcomes(self):
        """按批汇总：一次运行 1 条通知，计数覆盖 success/failed/skipped。

        替代逐条 started/failed/complete/abandoned（2026-09-21 实测逐条发导致
        1119 条通知中 622 条被 Telegram 429 拒绝）。
        """
        self._seed_announcement(1, "GB/T 5001-2020", "2026-01-01")
        self._seed_favorite(1, 1, retry_count=0, status="pending")
        self._seed_announcement(2, "GB/T 5002-2020", "2026-01-01")
        self._seed_favorite(1, 2, retry_count=0, status="pending")

        mode_by_record = {1: "success", 2: "fail"}
        processor = self.fcp

        def fake(favorite_id, user_id, record_id, notify=True):  # noqa: ARG001
            mode = mode_by_record.get(record_id, "success")
            self.raw.execute(
                "UPDATE favorite_downloads SET status=? WHERE favorite_id=?"
                " AND record_id=?",
                ("done" if mode == "success" else "failed", favorite_id, record_id),
            )
            self.raw.commit()

        with patch("pilotstd.tasks.favorite_download.download_to_inbox", side_effect=fake):
            with patch("pilotstd.manager.facade.StandardManager") as mock_mgr:
                processor.process_chain()

        notifier = mock_mgr.return_value.notification_mgr
        self.assertEqual(notifier.send_event.call_count, 1)
        event, payload = notifier.send_event.call_args[0]
        self.assertEqual(event, "batch_download_complete")
        self.assertEqual(payload["success"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["skipped"], 0)

    def test_failure_below_limit_does_not_notify_abandon(self):
        """未达上限的普通失败不得发放弃通知（避免刷屏）。"""
        self._seed_announcement(1, "GB/T 1002-2020", "2026-01-01")
        self._seed_favorite(1, 1, retry_count=0)
        self._dl_mode = "failed"

        with patch("pilotstd.manager.facade.StandardManager") as mock_mgr:
            self.fcp.process_pending_downloads()

        self.assertEqual(self._fd_status(1, 1)[0], "failed")
        mock_mgr.return_value.notification_mgr.send_event.assert_not_called()

    def test_abandon_notify_failure_does_not_break_chain(self):
        """通知抛异常不得影响状态机（放弃仍是终态）。"""
        self._seed_announcement(1, "GB/T 1003-2020", "2026-01-01")
        self._seed_favorite(1, 1, retry_count=self.fcp.MAX_RETRIES - 1)
        self._dl_mode = "failed"

        with patch(
            "pilotstd.manager.facade.StandardManager", side_effect=RuntimeError("notify boom")
        ):
            self.fcp.process_pending_downloads()

        self.assertEqual(self._fd_status(1, 1)[0], "abandoned")

    def _seed_user(self, user_id: int = 1) -> None:
        self.raw.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, salt, role)"
            " VALUES (?, ?, 'x', 'y', 'user')",
            (user_id, f"user{user_id}"),
        )
        self.raw.commit()

    def test_add_favorite_creates_favorite_downloads(self):
        """集成（断链修复核心）：add_favorite 成功后 favorite_downloads 新增 pending 行。"""
        from docker.api.favorites import FavoriteCreate, add_favorite
        from pilotstd.core.db.database import Database

        self._seed_user(1)
        self._seed_announcement(1, "GB/T 1001", "2026-01-01")
        db = Database(self.db_path)
        try:
            result = add_favorite(FavoriteCreate(record_id=1), user_id=1, db=db)
        finally:
            db.close()

        self.assertEqual(result["status"], "pending")
        row = self.raw.execute(
            "SELECT user_id, record_id, status, standard_no, standard_name"
            " FROM favorite_downloads WHERE user_id=1 AND record_id=1"
        ).fetchone()
        self.assertIsNotNone(row, "add_favorite 后 favorite_downloads 应有新行")
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 1)
        self.assertEqual(row[2], "pending")
        self.assertEqual(row[3], "GB/T 1001")
        self.assertEqual(row[4], "标准")

    def test_add_favorite_duplicate_no_duplicate_queue_row(self):
        """重复收藏：不新增 favorite_downloads 行（走 already_exists 分支）。"""
        from docker.api.favorites import FavoriteCreate, add_favorite
        from pilotstd.core.db.database import Database

        self._seed_user(1)
        self._seed_announcement(1, "GB/T 1001", "2026-01-01")
        db = Database(self.db_path)
        try:
            add_favorite(FavoriteCreate(record_id=1), user_id=1, db=db)
            result2 = add_favorite(FavoriteCreate(record_id=1), user_id=1, db=db)
        finally:
            db.close()
        self.assertEqual(result2["status"], "already_exists")
        count = self.raw.execute(
            "SELECT COUNT(*) FROM favorite_downloads WHERE user_id=1 AND record_id=1"
        ).fetchone()[0]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
