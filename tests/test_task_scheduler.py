# tests/test_task_scheduler.py
"""pilotstd/task/scheduler.py 单元测试 — 覆盖调度器生命周期、任务派发、异常处理。"""

from unittest.mock import MagicMock

from pilotstd.task.scheduler import TaskScheduler, get_scheduler


class TestTaskScheduler:
    """TaskScheduler 单元测试 — 不依赖真实数据库或 IO。"""

    def test_init_default(self):
        """初始化时 _queue 为 None，_running 为 False。"""
        s = TaskScheduler()
        assert s._queue is None
        assert s._running is False
        assert s.running is False

    def test_init_with_queue(self):
        """传入 TaskQueue 实例时应正确存储。"""
        mock_q = MagicMock()
        s = TaskScheduler(task_queue=mock_q)
        assert s._queue is mock_q

    def test_set_queue(self):
        """运行时注入 TaskQueue。"""
        s = TaskScheduler()
        mock_q = MagicMock()
        s.set_queue(mock_q)
        assert s._queue is mock_q

    def test_start_without_queue_warns(self):
        """队列未注入时 start 应跳过并警告。"""
        s = TaskScheduler()
        s.start()
        assert s._running is False
        assert s.running is False

    def test_start_twice_ignores_second(self):
        """重复 start 应不启动第二个线程。"""
        mock_q = MagicMock()
        mock_q.get_pending.return_value = []
        s = TaskScheduler(task_queue=mock_q)
        s.start()
        first_thread = s._thread
        s.start()
        assert s._thread is first_thread
        s.stop()

    def test_start_creates_daemon_thread(self):
        """start 应创建 daemon 后台线程。"""
        mock_q = MagicMock()
        mock_q.get_pending.return_value = []
        s = TaskScheduler(task_queue=mock_q)
        s.start()
        try:
            assert s._thread is not None
            assert s._thread.daemon is True
            assert s._thread.name == "task-sched"
        finally:
            s.stop()

    def test_stop_sets_stop_flag(self):
        """stop 应设置 _stop event 和 _running=False。"""
        mock_q = MagicMock()
        mock_q.get_pending.return_value = []
        s = TaskScheduler(task_queue=mock_q)
        s.start()
        s.stop()
        assert s._running is False
        assert s._stop.is_set()

    def test_stop_without_start_no_error(self):
        """未启动时 stop 不应抛异常。"""
        s = TaskScheduler()
        s.stop()
        assert s._running is False

    def test_run_polls_pending_tasks(self):
        """_run 应调用 get_pending 并派发任务。"""
        mock_q = MagicMock()
        task1 = MagicMock()
        task1.task_id = "task-1"
        task2 = MagicMock()
        task2.task_id = "task-2"
        call_count = [0]

        def side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return [task1, task2]
            s._stop.set()
            return []

        mock_q.get_pending.side_effect = side_effect
        s = TaskScheduler(task_queue=mock_q)
        s._running = True
        s._stop.wait = lambda timeout=None: None  # 加速测试
        s._run()
        assert mock_q.get_pending.call_count >= 1
        assert mock_q.start.call_count >= 1

    def test_run_handles_task_start_exception(self):
        """单个任务启动失败不应中断其他任务派发。"""
        mock_q = MagicMock()
        task1 = MagicMock()
        task1.task_id = "task-1"
        task2 = MagicMock()
        task2.task_id = "task-2"
        mock_q.start.side_effect = [RuntimeError("fail"), None]

        s = TaskScheduler(task_queue=mock_q)
        s._running = True
        # 加速测试：让 _stop.wait 立即返回
        s._stop.wait = lambda timeout=None: None
        call_n = [0]

        def poll_side_effect():
            call_n[0] += 1
            if call_n[0] == 1:
                return [task1, task2]
            s._stop.set()
            return []

        mock_q.get_pending.side_effect = poll_side_effect
        s._run()
        # task1 失败但 task2 仍被调用
        assert mock_q.start.call_count == 2

    def test_run_handles_get_pending_exception(self):
        """get_pending 异常不应中断调度循环。"""
        mock_q = MagicMock()
        mock_q.get_pending.side_effect = RuntimeError("db error")
        s = TaskScheduler(task_queue=mock_q)
        s._running = True
        s._stop.set()
        s._run()
        # 不应抛出异常

    def test_run_checks_stop_between_tasks(self):
        """_stop 被设置后应跳出任务循环。"""
        mock_q = MagicMock()
        task1 = MagicMock()
        task1.task_id = "task-1"
        task2 = MagicMock()
        task2.task_id = "task-2"
        mock_q.get_pending.return_value = [task1, task2]

        def set_stop(*args):
            s._stop.set()

        mock_q.start.side_effect = set_stop
        s = TaskScheduler(task_queue=mock_q)
        s._running = True
        s._run()
        # task1 启动后 stop 被设置，task2 不应被启动
        assert mock_q.start.call_count == 1


class TestGetScheduler:
    """get_scheduler 全局单例测试。"""

    def test_returns_singleton(self):
        """两次调用应返回同一个实例。"""
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_returns_task_scheduler_instance(self):
        """应返回 TaskScheduler 实例。"""
        s = get_scheduler()
        assert isinstance(s, TaskScheduler)
