"""pilotstd/monitor/scheduler.py 补测 — 单例/启停/禁用生命周期全覆盖。"""
import threading
from unittest.mock import MagicMock, patch

import pytest
from pilotstd.monitor.scheduler import FileMonitorScheduler, get_scheduler


@pytest.fixture(autouse=True)
def _reset_singleton():
    import pilotstd.monitor.scheduler as mod
    mod._instance = None


class TestGetScheduler:
    def test_returns_singleton(self):
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2
        assert isinstance(s1, FileMonitorScheduler)

    def test_reset_after_none(self):
        import pilotstd.monitor.scheduler as mod
        s1 = get_scheduler()
        mod._instance = None
        s2 = get_scheduler()
        assert s1 is not s2


class TestFileMonitorSchedulerInit:
    def test_default_state(self):
        s = FileMonitorScheduler()
        assert s.running is False
        assert s.observer is None
        assert s.handler is None
        assert isinstance(s._stop, threading.Event)

    def test_manager_injection(self):
        mgr = object()
        s = FileMonitorScheduler(manager=mgr)
        assert s._mgr is mgr


class TestStartStop:
    def test_start_when_disabled_skips(self):
        s = FileMonitorScheduler()
        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"enabled": False}
            s.start()
            assert s.running is False

    def test_start_when_already_running_skips(self):
        s = FileMonitorScheduler()
        s.running = True
        s.start()  # 不抛异常，直接返回

    def test_start_creates_thread_when_enabled(self):
        s = FileMonitorScheduler()
        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"enabled": True}
            with patch.object(s, "_run"):  # 跳过 watchdog 循环
                s.start()
                assert s._thread is not None
                assert s._thread.daemon is True
            s._stop.set()
            s._thread.join(timeout=3)

    def test_stop_sets_event_and_joins_thread(self):
        s = FileMonitorScheduler()
        s._thread = MagicMock()
        s.running = True
        s.stop()
        assert s._stop.is_set()
        s._thread.join.assert_called_once_with(timeout=5)

    def test_stop_with_observer_calls_stop(self):
        s = FileMonitorScheduler()
        s.observer = MagicMock()
        s._thread = MagicMock()
        s.stop()
        s.observer.stop.assert_called_once()


class TestOnFile:
    def test_auto_archive_disabled_skips(self):
        s = FileMonitorScheduler()
        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"auto_archive": False}
            with patch("pilotstd.monitor.scheduler.get_monitor_stats") as mock_stats:
                s._on_file("/path/to/file.pdf")
                mock_stats.return_value.increment.assert_not_called()

    def test_exception_increments_failed(self):
        s = FileMonitorScheduler()
        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"auto_archive": True}
            with patch("pilotstd.monitor.scheduler.get_monitor_stats") as mock_stats:
                s._mgr = MagicMock()
                s._mgr.scan_directory.side_effect = Exception("scan fail")
                s._on_file("/bad/path")
                mock_stats.return_value.increment.assert_any_call("failed")

    def test_no_manager_lazy_imports(self):
        s = FileMonitorScheduler()
        s._mgr = None
        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"auto_archive": True}
            with patch("pilotstd.monitor.scheduler.get_monitor_stats") as mock_stats:
                with patch("pilotstd.manager.facade.StandardManager") as MockMgr:
                    MockMgr.return_value.scan_directory.return_value = ["a", "b"]
                    s._on_file("/p/f.pdf")
                    assert s._mgr is not None


class TestGetStatus:
    def test_returns_status_dict(self):
        s = FileMonitorScheduler()
        s.running = False
        mock_stats = MagicMock()
        mock_stats.get_today_stats.return_value = {"processed": 10, "success": 8, "failed": 2}
        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"enabled": True, "watch_path": "/watch", "delay_seconds": 10}
            with patch("pilotstd.monitor.scheduler.get_monitor_stats", return_value=mock_stats):
                status = s.get_status()
                assert status["running"] is False
                assert status["enabled"] is True
                assert status["watch_path"] == "/watch"
                assert status["processed_today"] == 10
                assert status["failed_today"] == 2
