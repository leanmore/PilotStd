"""pilotstd/monitor/scheduler.py 补测 — 单例/启停/禁用生命周期全覆盖。"""
import logging
import threading
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.monitor.scheduler import (
    FileMonitorScheduler,
    get_scheduler,
    resolve_monitor_config,
)


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
            with patch("pilotstd.monitor.scheduler.get_monitor_stats"):
                with patch("pilotstd.manager.facade.StandardManager") as MockMgr:
                    MockMgr.return_value.scan_directory.return_value = ["a", "b"]
                    s._on_file("/p/f.pdf")
                    assert s._mgr is not None

    def test_empty_scan_result_logs_unrecognized(self, caplog):
        """解析不出标准号 → 明确告警（不再声称"扫描完成"，也不计 success）。

        技术债 #30：改前这里是 "扫描完成: 0 条" + 静默丢弃，面板看起来一切正常。
        """
        s = FileMonitorScheduler()
        s._mgr = MagicMock()
        s._mgr.scan_directory.return_value = []
        mock_stats = MagicMock()

        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"auto_archive": True}
            with patch(
                "pilotstd.monitor.scheduler.get_monitor_stats",
                return_value=mock_stats,
            ):
                with caplog.at_level(logging.WARNING):
                    s._on_file("/fake/path.pdf")

        assert "未识别到标准号，未归档" in caplog.text
        keys = [c.args[0] for c in mock_stats.increment.call_args_list]
        assert "failed" in keys and "success" not in keys


class TestResolveMonitorConfig:
    def test_env_override_takes_priority(self, monkeypatch):
        monkeypatch.setenv("PILOTSTD_STORAGE_INBOX_DIR", "/env/path")
        result = resolve_monitor_config({"watch_path": "/cfg/path"})
        assert result["watch_path"] == "/env/path"

    def test_cfg_fallback_when_no_env(self, monkeypatch):
        monkeypatch.delenv("PILOTSTD_STORAGE_INBOX_DIR", raising=False)
        result = resolve_monitor_config({"watch_path": "/cfg/path"})
        assert result["watch_path"] == "/cfg/path"

    def test_default_values(self):
        result = resolve_monitor_config({})
        assert result == {
            "watch_path": "/tmp/pilotstd-inbox",
            "delay_seconds": 5,
            "recursive": True,
        }

    def test_cfg_values_override_defaults(self):
        result = resolve_monitor_config({
            "watch_path": "/custom",
            "delay_seconds": 10,
            "recursive": False,
        })
        assert result["delay_seconds"] == 10
        assert result["recursive"] is False


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
