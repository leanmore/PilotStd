# tests/test_validity_config_api.py
"""G 修复回归：/api/validity/config 的运行期键读取。

历史缺陷：该端点读 `mgr.cfg`——进程启动时的内存快照，运行期从不 reload。
实测生产 API 返回 `next_run=2026-09-02`，而 2026-09-09 的运行日志已写入
`2026-09-16T03:00:00+00:00`，即端点永远滞后到容器启动那一刻的值。
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docker.api.validity import router as validity_router
from docker.manager import get_manager_dep


class TestValidityConfigApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(validity_router)
        cls.app = app
        cls.client = TestClient(app)

    def setUp(self):
        self.app.dependency_overrides.clear()
        self.app.dependency_overrides[get_manager_dep] = lambda: MagicMock()

    def _get(self, manager: MagicMock | None = None):
        if manager is not None:
            self.app.dependency_overrides[get_manager_dep] = lambda: manager
        # 始终隔离真实配置文件：端点内部会新建 ConfigManager 读盘
        self._cfg_patch = patch("pilotstd.core.config.ConfigManager")
        mock_cfg = self._cfg_patch.start()
        mock_cfg.return_value.get.side_effect = lambda key, default=None: {
            "validity.next_run": "2026-09-02T03:00:00+00:00",
            "validity.checked_count": 63,
            "validity.round_completed": False,
        }.get(key, default)
        self.addCleanup(self._cfg_patch.stop)
        resp = self.client.get("/api/validity/config")
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_next_run_prefers_live_scheduler_value(self):
        """调度器实时值优先于配置文件值。"""
        with patch("docker.scheduler.get_validity_next_run", return_value="2026-09-16T03:00:00+00:00"):
            data = self._get()
        self.assertEqual(data["next_run"], "2026-09-16T03:00:00+00:00")

    def test_next_run_falls_back_to_config_when_unscheduled(self):
        """调度器未注册该任务时回退配置文件值（不返回 null）。"""
        with patch("docker.scheduler.get_validity_next_run", return_value=None):
            data = self._get()
        self.assertEqual(data["next_run"], "2026-09-02T03:00:00+00:00")

    def test_does_not_read_manager_cfg_snapshot(self):
        """不得读取 mgr.cfg（进程启动快照）——读它即回归本次缺陷。"""
        mgr = MagicMock()
        mgr.cfg.get.side_effect = AssertionError("不应读取 mgr.cfg（进程启动快照）")
        with patch("docker.scheduler.get_validity_next_run", return_value=None):
            data = self._get(manager=mgr)
        self.assertEqual(data["checked_count"], 63)

    def test_scheduler_next_run_none_when_job_absent(self):
        """docker.scheduler.get_validity_next_run 在任务未注册时返回 None。"""
        from docker.scheduler import _VALIDITY_JOB_ID, get_validity_next_run, scheduler

        with patch.object(scheduler, "get_job", return_value=None) as get_job:
            self.assertIsNone(get_validity_next_run())
        get_job.assert_called_once_with(_VALIDITY_JOB_ID)

    def test_scheduler_next_run_returns_iso_when_scheduled(self):
        """任务已调度时返回其 next_run_time 的 ISO 字符串。"""
        from datetime import datetime, timedelta, timezone

        from docker.scheduler import get_validity_next_run, scheduler

        fire = datetime.now(timezone.utc) + timedelta(days=3)
        with patch.object(scheduler, "get_job") as get_job:
            get_job.return_value.next_run_time = fire
            self.assertEqual(get_validity_next_run(), fire.isoformat())
