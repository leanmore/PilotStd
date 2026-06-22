# tests/test_mock_pipeline.py
# Mock适配器单元测试 + Worker线程安全验证
"""用mock适配器测试下载逻辑，以及Worker线程控制，无需网络。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import threading
import time
import unittest

from pilotstd.download.models import DownloadTask
from tests.adapters.mock_download import MockDownloadAdapter


class TestMockDownloadAdapter(unittest.TestCase):
    """MockDownloadAdapter 独立单元测试——不依赖引擎。"""

    def test_can_handle_any_task(self):
        adapter = MockDownloadAdapter()
        self.assertTrue(adapter.can_handle(DownloadTask(standard_number="任意标准号")))
        self.assertTrue(
            adapter.can_handle(DownloadTask(standard_number="GB/T 19001-2016"))
        )

    def test_download_returns_pdf_content(self):
        adapter = MockDownloadAdapter()
        # 80%成功率，循环直到拿到一次成功结果
        for _ in range(20):
            task = DownloadTask(standard_number="GB 12345-2024")
            content = adapter.download(task)
            if content is not None:
                self.assertTrue(content.startswith(b"%PDF"))
                self.assertIn(b"GB 12345-2024", content)
                return
        self.skipTest("Mock适配器连续20次未返回结果（概率极低）")

    def test_download_failure_sets_error(self):
        adapter = MockDownloadAdapter()
        failures = 0
        for _ in range(50):
            task = DownloadTask(standard_number="GB 12345-2024")
            content = adapter.download(task)
            if content is None:
                failures += 1
                self.assertIn("模拟网络错误", task.error_message)
        self.assertGreater(failures, 0, "应至少有一次模拟失败")

    def test_site_name(self):
        adapter = MockDownloadAdapter()
        self.assertEqual(adapter.site_name, "mock_download")


class TestWorkerThreadSafety(unittest.TestCase):
    """Worker 停止/暂停/并发写DB测试。"""

    def test_pause_event_blocks_and_resumes(self):
        pause = threading.Event()
        pause.clear()
        result = {"ran": False}

        def worker():
            pause.wait()
            result["ran"] = True

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout=0.5)
        self.assertFalse(result["ran"], "pause.clear() 时 worker 应阻塞")
        pause.set()
        t.join(timeout=1)
        self.assertTrue(result["ran"], "pause.set() 后 worker 应恢复")

    def test_stop_flag_terminates_early(self):
        results = []
        stopped = threading.Event()

        def worker():
            for i in range(500):
                if stopped.is_set():
                    break
                results.append(i)
                time.sleep(0.005)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        time.sleep(0.3)
        stopped.set()
        t.join(timeout=3)
        self.assertLess(len(results), 500, "stop 后不应处理全部500条")
        self.assertGreater(len(results), 0, "至少应处理一些条目")

    def test_concurrent_sqlite_writes(self):
        """4线程同时写SQLite，WAL模式不应崩溃。"""
        tmpfile = os.path.join(os.path.dirname(__file__), "_test_concurrent.db")
        conn = sqlite3.connect(tmpfile)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER, val TEXT)")
        conn.close()

        errors = []

        def writer(thread_id: int):
            try:
                c = sqlite3.connect(tmpfile)
                for i in range(20):
                    c.execute(
                        "INSERT INTO t (id, val) VALUES (?, ?)",
                        (thread_id * 100 + i, f"t{thread_id}-{i}"),
                    )
                    c.commit()
                c.close()
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=writer, args=(i,), daemon=True) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], f"并发写入出错: {errors}")
        c = sqlite3.connect(tmpfile)
        count = c.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        c.close()
        self.assertEqual(count, 80, "应插入 4×20=80 条")

        os.remove(tmpfile)
        # 清理 WAL 文件
        for suffix in ("-wal", "-shm"):
            wal = tmpfile + suffix
            if os.path.exists(wal):
                os.remove(wal)
