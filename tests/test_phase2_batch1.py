"""批量补测: validity_service + monitor_service + expire。"""
from unittest.mock import MagicMock, patch
from pilotstd.manager.validity_service import ValidityService
from pilotstd.manager.monitor_service import MonitorService


class TestValidityService:
    def test_get_history(self):
        svc = ValidityService(MagicMock())
        svc._mgr.db.fetchone.return_value = {"cnt": 5}
        svc._mgr.db.fetchall.return_value = [
            {"check_date": "2026-01-15", "checked_count": 100, "changed_count": 3}
        ]
        r = svc.get_history(page=1, size=20)
        assert r["total"] == 5
        assert r["items"][0]["check_date"] == "2026-01-15"
        assert r["items"][0]["status"] == "success"

    def test_get_history_empty(self):
        svc = ValidityService(MagicMock())
        svc._mgr.db.fetchone.return_value = None
        svc._mgr.db.fetchall.return_value = []
        r = svc.get_history()
        assert r["total"] == 0
        assert r["items"] == []

    def test_enqueue_files(self):
        svc = ValidityService(MagicMock())
        r = svc.enqueue_files(["a.pdf", "b.pdf"])
        assert r["ok"] is True
        assert r["enqueued"] == 2
        assert r["total"] == 2

    def test_enqueue_files_exception_silent(self):
        svc = ValidityService(MagicMock())
        svc._mgr.db.execute.side_effect = Exception("db error")
        r = svc.enqueue_files(["bad.pdf"])
        assert r["ok"] is True
        assert r["enqueued"] == 0


class TestMonitorService:
    def test_get_config(self):
        svc = MonitorService(MagicMock())
        with patch("pilotstd.monitor.config.get_config", return_value={"enabled": True}):
            assert svc.get_config() == {"enabled": True}

    def test_set_config(self):
        svc = MonitorService(MagicMock())
        with patch("pilotstd.monitor.config.set_config") as mock_set:
            r = svc.set_config({"enabled": False})
            assert r["ok"] is True
            mock_set.assert_called_once_with({"enabled": False})

    def test_get_stats(self):
        svc = MonitorService(MagicMock())
        mock_stats = MagicMock()
        mock_stats.get_today_stats.return_value = {"processed": 5, "success": 4, "failed": 1}
        with patch("pilotstd.monitor.config.get_monitor_stats", return_value=mock_stats):
            r = svc.get_stats()
            assert r["processed"] == 5
            assert r["failed"] == 1

    def test_start_scheduler(self):
        svc = MonitorService(MagicMock())
        with patch("pilotstd.monitor.scheduler.get_scheduler") as mock_gs:
            svc.start_scheduler()
            mock_gs.return_value.start.assert_called_once()

    def test_stop_scheduler(self):
        svc = MonitorService(MagicMock())
        with patch("pilotstd.monitor.scheduler.get_scheduler") as mock_gs:
            svc.stop_scheduler()
            mock_gs.return_value.stop.assert_called_once()


class TestOrganizerExpire:
    def test_invalid_root_dir_returns_zero(self):
        from pilotstd.manager.organize.expire import OrganizerExpireMixin
        m = OrganizerExpireMixin()
        m._cfg = MagicMock()
        assert m.merge_expire_from_source("", []) == 0

    def test_empty_parsed_list_returns_zero(self):
        from pilotstd.manager.organize.expire import OrganizerExpireMixin
        m = OrganizerExpireMixin()
        m._cfg = MagicMock()
        assert m.merge_expire_from_source("/tmp", []) == 0
