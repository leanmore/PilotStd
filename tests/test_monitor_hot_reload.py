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
        # set_config 内部函数级 import get_scheduler，patch 其真实来源模块
        with patch("pilotstd.monitor.scheduler.get_scheduler", return_value=scheduler):
            with patch("pilotstd.monitor.config.set_config") as mock_set:
                with patch("pilotstd.monitor.config.get_config", return_value={"enabled": True}):
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

    def test_put_config_restart_exception_logged(self, service, caplog):
        """重启异常有 try/except 保护 + logger.error（结构化三字段）。"""
        import logging

        scheduler = MagicMock()
        scheduler.running = True
        scheduler.stop.side_effect = RuntimeError("stop fail")
        with patch("pilotstd.monitor.scheduler.get_scheduler", return_value=scheduler):
            with patch("pilotstd.monitor.config.set_config"):
                with patch("pilotstd.monitor.config.get_config", return_value={"enabled": True}):
                    with caplog.at_level(logging.ERROR, logger="pilotstd.manager.monitor_service"):
                        result = service.set_config({"watch_path": "/x"})
        # 异常被捕获，不抛出；返回 ok；错误日志含结构化字段
        assert result == {"ok": True}
        assert "监控服务重启失败" in caplog.text
        assert "trace_id=" in caplog.text
        assert "source_type=monitor_service" in caplog.text
        assert "target_chat_id=-" in caplog.text

    def test_put_config_starts_when_enabled_not_running(self, service):
        """服务未运行但 enabled=true → 启动（不重启）。"""
        scheduler = MagicMock()
        scheduler.running = False
        with patch("pilotstd.monitor.scheduler.get_scheduler", return_value=scheduler):
            with patch("pilotstd.monitor.config.set_config"):
                with patch("pilotstd.monitor.config.get_config", return_value={"enabled": True}):
                    service.set_config({"watch_path": "/x"})
        scheduler.stop.assert_not_called()
        scheduler.start.assert_called_once()
