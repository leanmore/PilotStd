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
        self.assertEqual(_job_funcs["test_job"], func)

    def test_register_job_func_overwrites_existing(self):
        func1 = MagicMock()
        func2 = MagicMock()
        register_job_func("test_job", func1)
        register_job_func("test_job", func2)
        self.assertEqual(_job_funcs["test_job"], func2)

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
            "tasks.auto_query_enabled": False,
            "tasks.auto_query_cron": "0 5 * * *",
            "tasks.auto_announce_enabled": False,
            "tasks.auto_announce_cron": "0 1 * * *",
        }.get(key, default)

        func = MagicMock()
        register_job_func("auto_scan", func)
        start_scheduler()

        # 只有 auto_scan 注册了，因为 enabled=True
        self.assertTrue(any(j.id == "auto_scan" for j in scheduler.get_jobs()))
        self.assertFalse(any(j.id == "auto_query" for j in scheduler.get_jobs()))

    @patch("docker.scheduler.ConfigManager")
    @patch.object(scheduler, "start")  # 避免前一个测试已启动导致 SchedulerAlreadyRunningError
    def test_start_scheduler_no_enabled_jobs_does_nothing(self, mock_start, mock_cfg):
        mock_cfg.return_value.get.return_value = False
        start_scheduler()
        self.assertEqual(len(scheduler.get_jobs()), 0)

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
