"""批次4-D组：监控热更新测试 — PUT 配置后触发 stop→start 周期。

用例 2/3（enabled=false 阻断启动 / stop 重置 running）在现有
test_monitor_scheduler.py 已部分覆盖（功能已实现），本文件以独立用例
锁定回归；用例 1（PUT 触发重启）为批次 4 核心缺口修复的测试先行锁定。
"""
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.manager.monitor_service import MonitorService


@pytest.fixture
def service():
    """构造 MonitorService 实例（不触发全局单例副作用）。"""
    mgr = MagicMock()
    return MonitorService(mgr)


class TestMonitorHotReload:
    def test_put_config_triggers_restart(self, service):
        """PUT 新配置后，scheduler 经历 stop→start 周期（mock 验证调用次数）。

        修复前：set_config 只写配置不重启 → stop/start 均未调用（FAIL）。
        """
        scheduler = MagicMock()
        scheduler.running = True
        with patch("pilotstd.manager.monitor_service.get_scheduler", return_value=scheduler) as mock_get:
            with patch("pilotstd.monitor.config.set_config") as mock_set:
                service.set_config({"watch_path": "/new/path"})
                mock_set.assert_called_once_with({"watch_path": "/new/path"})
        # 核心断言：运行中 → 重启（stop + start 各一次）
        scheduler.stop.assert_called_once()
        scheduler.start.assert_called_once()

    def test_enabled_false_blocks_start(self):
        """enabled=false 时调用 start() → running 保持 False。"""
        from pilotstd.monitor.scheduler import FileMonitorScheduler

        s = FileMonitorScheduler()
        with patch("pilotstd.monitor.scheduler.get_config") as mock_cfg:
            mock_cfg.return_value = {"enabled": False}
            s.start()
            assert s.running is False

    def test_stop_resets_running_flag(self):
        """stop() 后 scheduler.running is False。"""
        from pilotstd.monitor.scheduler import FileMonitorScheduler

        s = FileMonitorScheduler()
        s.running = True
        s._thread = MagicMock()
        s.stop()
        assert s.running is False
        assert s._stop.is_set()
