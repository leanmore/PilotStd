# tests/test_task_history.py
# Phase2: task_execution_history 表 — 单元测试 + 集成测试 + 性能基线

import os
import sys
import tempfile
import time
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.core.db.database import Database
from pilotstd.core.db.migrations import _migrate_v47_task_execution_history
from pilotstd.core.task_history import _set_db_override


def _setup_test_db() -> Database:
    """创建临时测试数据库并运行 v47 迁移。"""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    db = Database(db_path)
    _migrate_v47_task_execution_history(db)
    return db, tmpdir


class TestTaskHistoryCommon(unittest.TestCase):
    """所有 task_history 测试的基类，统一管理 DB 覆盖。"""

    db: Database
    _tmpdir: str

    @classmethod
    def setUpClass(cls):
        cls.db, cls._tmpdir = _setup_test_db()
        _set_db_override(cls.db)

    @classmethod
    def tearDownClass(cls):
        _set_db_override(None)
        cls.db.close()
        import shutil

        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def setUp(self):
        self.db.execute("DELETE FROM task_execution_history")
        import pilotstd.core.task_history as mod

        mod._write_count = 0


class TestTaskHistoryWrite(TestTaskHistoryCommon):
    """write_execution_record() — 写入 + 查询 + 内存缓存更新。"""

    def test_write_and_read(self):
        from pilotstd.core.task_history import get_task_history, write_execution_record

        write_execution_record("scan", "success", duration_ms=42)
        write_execution_record("scan", "error", "timeout", 5000)
        result = get_task_history("scan", page=1, size=10)
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["status"], "error")

    def test_write_updates_memory_cache(self):
        from pilotstd.core.task_history import write_execution_record
        from pilotstd.core.task_status import get_task_status

        write_execution_record("cache_test", "success")
        cached = get_task_status("cache_test")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["last_run_status"], "success")

    def test_duration_recorded(self):
        from pilotstd.core.task_history import get_task_history, write_execution_record

        write_execution_record("dur_test", "success", duration_ms=1234)
        result = get_task_history("dur_test", page=1, size=1)
        self.assertEqual(result["items"][0]["duration_ms"], 1234)


class TestTaskHistoryPagination(TestTaskHistoryCommon):
    """get_task_history() — 分页边界测试。"""

    def test_page1_size5_30_records(self):
        from pilotstd.core.task_history import get_task_history, write_execution_record

        for i in range(30):
            write_execution_record("paging", "success")
        result = get_task_history("paging", page=1, size=5)
        self.assertEqual(result["total"], 30)
        self.assertEqual(len(result["items"]), 5)

    def test_page_beyond_range_returns_empty(self):
        from pilotstd.core.task_history import get_task_history

        result = get_task_history("empty_task", page=99, size=10)
        self.assertEqual(result["total"], 0)
        self.assertEqual(len(result["items"]), 0)

    def test_size_min_clamped(self):
        from pilotstd.core.task_history import get_task_history, write_execution_record

        write_execution_record("clamp", "success")
        result = get_task_history("clamp", page=1, size=0)
        self.assertGreaterEqual(result["size"], 1)


class TestTaskHistoryCleanup(TestTaskHistoryCommon):
    """_cleanup_if_needed() — 30天过期 + 单任务2000条上限。"""

    def test_cleanup_triggered_at_threshold(self):
        import pilotstd.core.task_history as mod
        from pilotstd.core.task_history import write_execution_record

        mod._write_count = 9
        write_execution_record("throttle", "success")
        self.assertEqual(mod._write_count, 10)

    def test_2000_limit_per_task(self):
        import pilotstd.core.task_history as mod
        from pilotstd.core.task_history import get_task_history, write_execution_record

        for i in range(2010):
            self.db.execute(
                "INSERT INTO task_execution_history (task_name, status, finished_at)"
                " VALUES ('overflow_test', 'success', datetime('now', ? || ' seconds'))",
                (str(-i),),
            )
        mod._write_count = 9
        write_execution_record("overflow_test", "success")

        result = get_task_history("overflow_test", page=1, size=10)
        self.assertLessEqual(result["total"], 2000)

    def test_30day_expiry(self):
        import pilotstd.core.task_history as mod
        from pilotstd.core.task_history import get_task_history, write_execution_record

        self.db.execute(
            "INSERT INTO task_execution_history (task_name, status, finished_at)"
            " VALUES ('old_task', 'success', datetime('now', '-31 days'))"
        )
        self.db.execute(
            "INSERT INTO task_execution_history (task_name, status, finished_at)"
            " VALUES ('old_task', 'success', datetime('now'))"
        )
        mod._write_count = 9
        write_execution_record("trigger", "success")

        result = get_task_history("old_task", page=1, size=10)
        self.assertEqual(result["total"], 1)


class TestTaskHistoryStats(TestTaskHistoryCommon):
    """get_task_stats() — 聚合统计正确性。"""

    def test_success_rate_calculation(self):
        from pilotstd.core.task_history import get_task_stats, write_execution_record

        write_execution_record("rate_test", "success", duration_ms=100)
        write_execution_record("rate_test", "success", duration_ms=200)
        write_execution_record("rate_test", "error", "fail", 50)
        write_execution_record("rate_test", "success", duration_ms=300)

        stats = get_task_stats()
        t = next(s for s in stats if s["task_name"] == "rate_test")
        self.assertEqual(t["total_count"], 4)
        self.assertAlmostEqual(t["success_rate"], 0.75, delta=0.01)

    def test_last_error_captured(self):
        from pilotstd.core.task_history import get_task_stats, write_execution_record

        write_execution_record("err_test", "error", "last error", 20)

        stats = get_task_stats()
        t = next(s for s in stats if s["task_name"] == "err_test")
        self.assertIn("last error", t["last_error"])


class TestDecoratorIntegration(TestTaskHistoryCommon):
    """capture_task_error 装饰器 → DB 写入端到端。"""

    def test_decorator_writes_db_on_success(self):
        from pilotstd.core.task_status import capture_task_error

        @capture_task_error("deco_test")
        def sample_task():
            return "ok"

        result = sample_task()
        self.assertEqual(result, "ok")

        rows = self.db.fetchall("SELECT * FROM task_execution_history WHERE task_name='deco_test'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "success")

    def test_decorator_writes_db_on_error(self):
        from pilotstd.core.task_status import capture_task_error

        @capture_task_error("deco_fail")
        def failing_task():
            raise ValueError("simulated failure")

        result = failing_task()
        self.assertIsNone(result)

        rows = self.db.fetchall("SELECT * FROM task_execution_history WHERE task_name='deco_fail'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "error")
        self.assertIn("simulated failure", rows[0]["error_message"] or "")

    def test_memory_cache_consistent_with_db(self):
        from pilotstd.core.task_status import capture_task_error, get_task_status

        @capture_task_error("consistency_check")
        def quick_task():
            return 42

        quick_task()
        cached = get_task_status("consistency_check")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["last_run_status"], "success")

        rows = self.db.fetchall("SELECT * FROM task_execution_history WHERE task_name='consistency_check'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "success")


class TestPerformanceBaseline(TestTaskHistoryCommon):
    """大数据量下 history 列表查询 P95 < 50ms。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Database.execute() 自动提交，每条 INSERT 独立事务
        for i in range(10000):
            cls.db.execute(
                "INSERT INTO task_execution_history (task_name, status, finished_at, duration_ms)"
                " VALUES (?, 'success', datetime('now', ? || ' seconds'), ?)",
                (f"perf_{i % 10}", str(-i), i % 100),
            )

    def setUp(self):
        pass  # 不清理数据——setUpClass 中的批量插入数据需要保留

    def test_history_query_p95_under_50ms(self):
        from pilotstd.core.task_history import get_task_history

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            get_task_history(page=2, size=20)
            latencies.append((time.perf_counter() - start) * 1000)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        self.assertLess(p95, 50, f"P95={p95:.1f}ms 超过 50ms 阈值")

    def test_stats_query_fast(self):
        from pilotstd.core.task_history import get_task_stats

        start = time.perf_counter()
        stats = get_task_stats()
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertGreater(len(stats), 0)
        self.assertLess(elapsed_ms, 200, f"stats query {elapsed_ms:.1f}ms 过慢")


if __name__ == "__main__":
    unittest.main()
