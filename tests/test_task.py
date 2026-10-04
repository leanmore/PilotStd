# tests/test_task.py

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import time
import unittest

import pytest

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
    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        self.queue = TaskQueue(shared_db)
        # 清理上一个测试的残留任务数据
        shared_db.execute("DELETE FROM task_queue")

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

    def test_clear_finished_deletes_only_finished(self):
        """W1：清除已完成必须**真删**（旧实现只把状态改成 CANCELLED，列表照旧显示）。"""
        done = self.queue.enqueue(TaskType.SCAN, total_items=1)
        self.queue.update_progress(done, completed=1)  # → COMPLETED
        failed = self.queue.enqueue(TaskType.QUERY, total_items=1)
        self.queue.update_progress(failed, completed=0, failed=1)  # → COMPLETED（计数达总数）
        gone = self.queue.enqueue(TaskType.DOWNLOAD, total_items=1)
        self.queue.cancel(gone.task_id)  # → CANCELLED
        running = self.queue.enqueue(TaskType.ORGANIZE, total_items=10)  # 仍在进行中

        removed = self.queue.clear_finished()
        self.assertGreaterEqual(removed, 3)
        remaining = {t.task_id for t in self.queue.list_all(limit=50)}
        self.assertIn(running.task_id, remaining, "进行中的任务不得被清除")
        self.assertNotIn(done.task_id, remaining)
        self.assertNotIn(gone.task_id, remaining)

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


class TestTaskWriterMapping(unittest.TestCase):
    """任务写入方（`_dialog_ops._register_task`）的业务名 → TaskType 映射。"""

    def _run(self, label: str):
        """用最小窗口替身调用 `_register_task`，返回入队时用的 TaskType。"""
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from pilotstd.ui.main_window.parts._dialog_ops import _register_task

        queue = MagicMock()
        queue.enqueue.return_value = SimpleNamespace()
        window = SimpleNamespace(_mgr=SimpleNamespace(task_queue=queue))
        _register_task(window, label, total=3, completed=3, failed=0)
        return queue.enqueue.call_args.args[0]

    def test_all_five_business_names_mapped(self):
        """W1/W4：扫描/查询/下载/规范化/过期处理 五类都必须映射到各自的 TaskType。"""
        from pilotstd.task.models import TaskType

        expected = {
            "扫描": TaskType.SCAN,
            "查询": TaskType.QUERY,
            "下载": TaskType.DOWNLOAD,
            "规范化": TaskType.ORGANIZE,
            "过期处理": TaskType.EXPIRE,
        }
        for label, task_type in expected.items():
            with self.subTest(label=label):
                self.assertEqual(self._run(label), task_type)

    def test_unknown_label_falls_back_to_scan(self):
        """未知业务名回退 SCAN（既有兜底口径不变）。"""
        from pilotstd.task.models import TaskType

        self.assertEqual(self._run("未知操作"), TaskType.SCAN)
