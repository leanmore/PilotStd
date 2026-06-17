# tests/test_task.py

import sys
import os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest
import tempfile
import shutil
import time

from pilotstd.core.db import Database
from pilotstd.task.models import TaskInfo, TaskStatus, TaskType
from pilotstd.task.queue import TaskQueue


class TestTaskModels(unittest.TestCase):
    def test_progress_pct(self):
        t = TaskInfo(total_items=100, completed_items=45)
        self.assertAlmostEqual(t.progress_pct, 45.0)

    def test_progress_zero_total(self):
        t = TaskInfo(total_items=0, completed_items=0)
        self.assertEqual(t.progress_pct, 0.0)


class TestTaskQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = Database(os.path.join(self.tmp, "test.db"))
        self.queue = TaskQueue(self.db)

    def tearDown(self):
        self.db.close()
        self.db = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_enqueue_and_get(self):
        task = self.queue.enqueue(TaskType.SCAN, total_items=10)
        self.assertEqual(task.status, TaskStatus.PENDING)
        fetched = self.queue.get(task.task_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.total_items, 10)

    def test_pause_and_cancel(self):
        task = self.queue.enqueue(TaskType.QUERY, total_items=5)
        self.queue.pause(task.task_id)
        t = self.queue.get(task.task_id)
        self.assertEqual(t.status, TaskStatus.PAUSED)

        self.queue.cancel(task.task_id)
        t = self.queue.get(task.task_id)
        self.assertEqual(t.status, TaskStatus.CANCELLED)

    def test_list_all(self):
        for i in range(3):
            self.queue.enqueue(TaskType.DOWNLOAD, total_items=i)
        tasks = self.queue.list_all(limit=10)
        self.assertGreaterEqual(len(tasks), 3)

    def test_get_pending(self):
        self.queue.enqueue(TaskType.SCAN)
        self.queue.enqueue(TaskType.QUERY)
        pending = self.queue.get_pending()
        self.assertEqual(len(pending), 2)

    def test_update_progress(self):
        task = self.queue.enqueue(TaskType.ORGANIZE, total_items=5)
        self.queue.update_progress(task, completed=5)
        t = self.queue.get(task.task_id)
        self.assertEqual(t.status, TaskStatus.COMPLETED)

    def test_handler_execution(self):
        handler_called = []

        def my_handler(t: TaskInfo) -> TaskInfo:
            handler_called.append(True)
            t.completed_items = t.total_items
            return t

        self.queue.register_handler(TaskType.SCAN, my_handler)
        task = self.queue.enqueue(TaskType.SCAN, total_items=1)
        self.queue.start(task)

        time.sleep(0.2)
        t = self.queue.get(task.task_id)
        self.assertTrue(handler_called)
        self.assertEqual(t.status, TaskStatus.COMPLETED)

    def test_failed_handler(self):
        def bad_handler(t: TaskInfo) -> TaskInfo:
            raise RuntimeError("模拟异常")

        self.queue.register_handler(TaskType.EXPIRE, bad_handler)
        task = self.queue.enqueue(TaskType.EXPIRE, total_items=1)
        self.queue.start(task)

        time.sleep(0.2)
        t = self.queue.get(task.task_id)
        self.assertEqual(t.status, TaskStatus.FAILED)
        self.assertIn("模拟异常", t.error_log)

    def test_handler_timeout(self):
        """handler 执行超过 timeout 应标记为 FAILED。"""
        def slow_handler(t: TaskInfo) -> TaskInfo:
            time.sleep(10)
            return t

        queue = TaskQueue(self.db, task_timeout=1)
        queue.register_handler(TaskType.SCAN, slow_handler)
        task = queue.enqueue(TaskType.SCAN, total_items=1)
        queue.start(task)

        # 轮询等待超时触发（最多等 5s）
        for _ in range(50):
            t = queue.get(task.task_id)
            if t.status == TaskStatus.FAILED:
                break
            time.sleep(0.1)
        else:
            t = queue.get(task.task_id)
        self.assertEqual(t.status, TaskStatus.FAILED)
        self.assertIn("超时", t.error_log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
