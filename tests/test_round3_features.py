# tests/test_round3_features.py
"""第三轮功能测试：静音时段 + 公告统计 + 管道历史"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.manager import get_manager_dep


class TestQuietHours(unittest.TestCase):
    """静音时段入队与补发逻辑"""

    @classmethod
    def setUpClass(cls):
        from pilotstd.core.notification.manager import NotificationManager

        cls.NotificationManager = NotificationManager

    def test_is_quiet_hours_false_when_disabled(self):
        cfg = MagicMock()
        cfg._filepath = os.path.join(os.path.dirname(__file__), "test_config.json")
        cfg.get.return_value = False
        mgr = self.NotificationManager(cfg, MagicMock(), user_id=1)
        self.assertFalse(mgr._is_quiet_hours())

    def test_is_quiet_hours_true_when_inside(self):
        cfg = MagicMock()
        cfg._filepath = os.path.join(os.path.dirname(__file__), "test_config.json")

        def _cfg_get(key, default=None):
            return {
                "notification.quiet_hours_enabled": True,
                "notification.quiet_hours_start": "22:00",
                "notification.quiet_hours_end": "07:00",
            }.get(key, default)

        cfg.get.side_effect = _cfg_get
        mgr = self.NotificationManager(cfg, MagicMock(), user_id=1)
        # 直接 patch manager 模块中已导入的 datetime
        with patch("pilotstd.core.notification.manager.datetime") as mock_dt:
            fake_now = MagicMock()
            fake_now.time.return_value = __import__("datetime").time(3, 0)
            mock_dt.now.return_value = fake_now
            mock_dt.strptime.side_effect = lambda s, f: __import__("datetime").datetime.strptime(s, f)
            self.assertTrue(mgr._is_quiet_hours())

    def test_enqueue_writes_to_queue(self):
        cfg = MagicMock()
        cfg._filepath = os.path.join(os.path.dirname(__file__), "test_config.json")

        def _cfg_get(key, default=None):
            return {
                "notification.quiet_hours_enabled": True,
                "notification.quiet_hours_start": "22:00",
                "notification.quiet_hours_end": "07:00",
            }.get(key, default)

        cfg.get.side_effect = _cfg_get
        mock_db = MagicMock()
        mgr = self.NotificationManager(cfg, mock_db, user_id=1)
        msg = MagicMock()
        msg.event_type = "test"
        msg.title = "T"
        msg.body = "B"
        msg.level = "info"
        msg.link = None
        msg.icon = None
        mgr._enqueue_notification(msg, ["wechat"])
        # 验证 db.execute 被调用且 SQL 含 INSERT INTO notification_queue
        calls = [str(c) for c in mock_db.execute.call_args_list]
        self.assertTrue(any("INSERT INTO notification_queue" in c for c in calls))

    def test_release_suppressed_returns_zero_when_empty(self):
        cfg = MagicMock()
        cfg._filepath = os.path.join(os.path.dirname(__file__), "test_config.json")
        cfg.get.return_value = False
        mock_db = MagicMock()
        mock_db.fetchall.return_value = []
        mgr = self.NotificationManager(cfg, mock_db, user_id=1)
        self.assertEqual(mgr.release_suppressed_notifications(), 0)


class TestAnnounceStats(unittest.TestCase):
    """公告统计 API"""

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        from docker.api.announce import router as announce_router

        app.include_router(announce_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.app.dependency_overrides.clear()

    def test_stats_returns_200_with_expected_structure(self):
        """统计接口返回正确的 JSON 结构。"""
        mock_mgr = MagicMock()
        # fetchone 被多次调用：all_row, today_row, matched_row
        mock_mgr.db.fetchone.side_effect = [
            {"total": 500, "gb": 300, "hb": 50, "db": 150},  # all_row (全量)
            {"total": 10, "gb": 5, "hb": 3, "db": 2},  # today_row
            {"cnt": 7},  # matched_row
        ]
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.get("/api/announce/stats")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("total", data)
        self.assertIn("matched", data)
        self.assertIn("new", data)
        self.assertNotIn("updated", data)
        self.assertNotIn("failed", data)
        self.assertEqual(data["total"]["all"], 500)  # 全量
        self.assertEqual(data["total"]["gb"], 300)
        self.assertEqual(data["matched"], 7)
        self.assertEqual(data["new"]["all"], 10)  # 今日新增 = today_row.total

    def test_stats_cache_returns_same_data(self):
        """连续两次请求返回相同数据（5分钟内存缓存）。"""
        mock_mgr = MagicMock()
        mock_mgr.db.fetchone.side_effect = [
            {"total": 500, "gb": 300, "hb": 50, "db": 150},  # all_row
            {"total": 10, "gb": 5, "hb": 3, "db": 2},  # today_row
            {"cnt": 7},  # matched_row
        ]
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r1 = self.client.get("/api/announce/stats")
        r2 = self.client.get("/api/announce/stats")
        self.assertEqual(r1.json(), r2.json())


class TestPipelineRuns(unittest.TestCase):
    """管道历史 API"""

    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        from docker.api.tasks import router as tasks_router

        app.include_router(tasks_router)
        cls.client = TestClient(app)

    def setUp(self):
        self.client.app.dependency_overrides.clear()

    def test_runs_list_returns_pagination_structure(self):
        """分页接口返回标准 {total, page, page_size, items} 结构。"""
        mock_mgr = MagicMock()
        mock_mgr.db.fetchone.return_value = {"cnt": 0}
        mock_mgr.db.fetchall.return_value = []
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.get("/api/tasks/runs?page=1&page_size=20")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("total", data)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 20)
        self.assertIsInstance(data["items"], list)

    def test_runs_list_default_page_size(self):
        """无参数时默认 page=1, page_size=20。"""
        mock_mgr = MagicMock()
        mock_mgr.db.fetchone.return_value = {"cnt": 0}
        mock_mgr.db.fetchall.return_value = []
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.get("/api/tasks/runs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["page"], 1)
        self.assertEqual(r.json()["page_size"], 20)

    def test_runs_respects_custom_page_size(self):
        """自定义分页参数正确传递。"""
        mock_mgr = MagicMock()
        mock_mgr.db.fetchone.return_value = {"cnt": 50}
        mock_mgr.db.fetchall.return_value = [{"run_id": f"r{i}"} for i in range(5)]
        self.client.app.dependency_overrides[get_manager_dep] = lambda: mock_mgr
        r = self.client.get("/api/tasks/runs?page=2&page_size=5")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["page"], 2)
        self.assertEqual(r.json()["page_size"], 5)
