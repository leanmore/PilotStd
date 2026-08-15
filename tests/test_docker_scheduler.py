# tests/test_docker_scheduler.py
"""docker/scheduler.py 定时任务模块测试"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch

from docker.scheduler import (
    _job_funcs,
    register_job_func,
    scheduler,
    start_scheduler,
    stop_scheduler,
    update_job,
)


class TestSchedulerModule(unittest.TestCase):
    def setUp(self):
        _job_funcs.clear()
        # 暂停调度器并移除所有任务（避免 shutdown 导致无法重启）
        if scheduler.running:
            scheduler.pause()
        for job in scheduler.get_jobs():
            scheduler.remove_job(job.id)

    def tearDown(self):
        # 暂停 + 清空，不调用 shutdown（shutdown 后无法重启）
        if scheduler.running:
            scheduler.pause()
        for job in scheduler.get_jobs():
            scheduler.remove_job(job.id)
        _job_funcs.clear()

    def test_register_job_func_stores_callable(self):
        func = MagicMock()
        register_job_func("test_job", func)
        self.assertIn("test_job", _job_funcs)
        stored = _job_funcs["test_job"]
        self.assertTrue(callable(stored), "注册后的函数应可调用")
        # 验证包装后的函数执行原逻辑（不抛异常即通过）
        func.return_value = 42
        result = stored()
        func.assert_called_once()
        self.assertEqual(result, 42)

    def test_register_job_func_overwrites_existing(self):
        func1 = MagicMock()
        func2 = MagicMock()
        register_job_func("test_job", func1)
        register_job_func("test_job", func2)
        # Phase1 装饰器包装后不再直接持有原始引用，验证可调用 + 最新函数被执行
        stored = _job_funcs["test_job"]
        self.assertTrue(callable(stored))
        func1.return_value = "old"
        func2.return_value = "new"
        result = stored()
        self.assertFalse(func1.called, "func1 不应被调用")
        self.assertTrue(func2.called, "func2 应被调用")
        self.assertEqual(result, "new")

    def test_job_func_not_called_on_register(self):
        """注册只存储，不立即执行"""
        func = MagicMock()
        register_job_func("test_job", func)
        func.assert_not_called()

    @patch("docker.scheduler.ConfigManager")
    def test_start_scheduler_adds_enabled_jobs(self, mock_cfg):
        mock_cfg.return_value.get.side_effect = lambda key, default: {
            "tasks.auto_scan_enabled": True,
            "tasks.auto_scan_cron": "0 3 * * *",
            "tasks.auto_announce_enabled": False,
            "tasks.auto_announce_cron": "0 1 * * *",
        }.get(key, default)

        func = MagicMock()
        register_job_func("auto_scan", func)
        start_scheduler()

        # 只有 auto_scan 注册了，因为 enabled=True
        self.assertTrue(any(j.id == "auto_scan" for j in scheduler.get_jobs()))

    @patch("docker.scheduler.ConfigManager")
    @patch.object(scheduler, "start")  # 避免前一个测试已启动导致 SchedulerAlreadyRunningError
    def test_start_scheduler_no_enabled_jobs_does_nothing(self, mock_start, mock_cfg):
        mock_cfg.return_value.get.return_value = False
        start_scheduler()
        self.assertEqual(len(scheduler.get_jobs()), 0)

    @patch("docker.scheduler._add_cron_job")
    @patch("docker.scheduler._acquire_scheduler_lock", return_value=True)
    @patch.object(scheduler, "start")
    @patch("docker.scheduler.ConfigManager")
    def test_auto_announce_fallback_cron_is_0100(self, mock_cfg, mock_start, _mock_lock, mock_add):
        """auto_announce 未显式配置 cron 时，fallback 应为 0 1 * * *（避免与整点健康检查撞车）。"""
        mock_cfg.return_value.get.side_effect = lambda key, default: {
            "tasks.auto_announce_enabled": True,
        }.get(key, default)

        register_job_func("auto_announce", MagicMock())
        start_scheduler()

        announce_calls = [c for c in mock_add.call_args_list if c[0][0] == "auto_announce"]
        self.assertEqual(len(announce_calls), 1)
        self.assertEqual(announce_calls[0][0][1], "0 1 * * *")

    def test_update_job_adds_when_not_exists(self):
        func = MagicMock()
        register_job_func("auto_scan", func)
        update_job("auto_scan", "0 3 * * *", True)
        self.assertTrue(any(j.id == "auto_scan" for j in scheduler.get_jobs()))

    def test_update_job_removes_when_disabled(self):
        func = MagicMock()
        register_job_func("auto_scan", func)
        update_job("auto_scan", "0 3 * * *", True)  # add first
        update_job("auto_scan", "0 3 * * *", False)  # then disable
        self.assertFalse(any(j.id == "auto_scan" for j in scheduler.get_jobs()))

    def test_update_job_does_nothing_for_unknown_job(self):
        update_job("nonexistent", "0 3 * * *", True)
        self.assertFalse(any(j.id == "nonexistent" for j in scheduler.get_jobs()))

    @patch.object(scheduler, "shutdown")
    def test_stop_scheduler_shuts_down(self, mock_shutdown):
        """stop_scheduler 应调用 scheduler.shutdown()，此处用 mock 避免真销毁"""
        stop_scheduler()
        mock_shutdown.assert_called_once()

    def test_date_reminder_wrapper_raises_on_failure(self):
        """_date_reminder_wrapper 应在 date_reminder 失败时冒泡异常，避免假 success。"""
        from docker.scheduler import _date_reminder_wrapper

        with patch("docker.scheduler.run_date_reminder", side_effect=Exception("SQL error")):
            with self.assertRaises(Exception):
                _date_reminder_wrapper(notification_mgr=MagicMock())
