"""pilotstd/platform/notify.py 补测 — NotifyService 单例/去重/降级全覆盖。"""
import time
from unittest.mock import MagicMock, patch

import pytest
from pilotstd.platform.notify import NotifyService


@pytest.fixture(autouse=True)
def _reset_singleton():
    """每个测试前重置单例。"""
    NotifyService._instance = None


class TestNotifyServiceSingleton:
    """单例模式 — 正常×2 + 边界×1。"""

    def test_normal_init_and_get(self):
        """init 后 get 返回同一实例。"""
        mock_tray = MagicMock()
        NotifyService.init(mock_tray)
        svc = NotifyService.get()
        assert svc is NotifyService._instance
        assert svc._tray is mock_tray

    def test_normal_get_without_init_silent_degradation(self):
        """未 init 时 get 静默降级（tray=None 的单例）。"""
        svc = NotifyService.get()
        assert svc is not None
        assert svc._tray is None
        # show 调用不崩溃
        svc.show("title", "message")

    def test_boundary_multiple_init_overwrites(self):
        """多次 init 覆盖单例。"""
        tray1 = MagicMock()
        tray2 = MagicMock()
        NotifyService.init(tray1)
        assert NotifyService.get()._tray is tray1
        NotifyService.init(tray2)
        assert NotifyService.get()._tray is tray2


class TestNotifyServiceShow:
    """通知发送 — 正常×2 + 边界×1 + 状态转换×1。"""

    def test_normal_show_calls_tray_show_message(self):
        """enabled + tray 存在时，show 调用 QSystemTrayIcon.showMessage。"""
        mock_tray = MagicMock()
        svc = NotifyService(mock_tray)
        svc._enabled = True

        with patch.object(svc, "_get_aggregator") as mock_agg:
            mock_agg.return_value.auto_pause_enabled = False
            svc.show("Test Title", "Test Body", 3000)
            mock_tray.showMessage.assert_called_once()

    def test_normal_show_warning_calls_with_warning_icon(self):
        """show_warning 正确传递参数（非聚合器路径）。"""
        mock_tray = MagicMock()
        svc = NotifyService(mock_tray)
        svc._enabled = True

        with patch.object(svc, "_get_aggregator") as mock_agg:
            mock_agg.return_value.auto_pause_enabled = False
            svc.show_warning("Warn", "Something wrong", 4000)
            mock_tray.showMessage.assert_called_once()

    def test_boundary_disabled_does_not_show(self):
        """enabled=False 时不发送通知。"""
        mock_tray = MagicMock()
        svc = NotifyService(mock_tray)
        svc._enabled = False
        svc.show("Title", "Body")
        mock_tray.showMessage.assert_not_called()

    def test_state_enabled_toggle(self):
        """enabled 属性读写正确控制发送行为。"""
        mock_tray = MagicMock()
        svc = NotifyService(mock_tray)
        assert svc.enabled is True

        svc.enabled = False
        svc.show("T", "M")
        mock_tray.showMessage.assert_not_called()

        svc.enabled = True
        with patch.object(svc, "_get_aggregator") as mock_agg:
            mock_agg.return_value.auto_pause_enabled = False
            svc.show("T2", "M2")
            mock_tray.showMessage.assert_called_once()


class TestCheckDedup:
    """去重逻辑 — 正常×2 + 边界×1 + 状态转换×1。"""

    def test_normal_first_call_returns_true(self):
        """首次调用去重检查返回 True。"""
        svc = NotifyService(None)
        assert svc._check_dedup("new_title") is True

    def test_normal_same_title_within_window_returns_false(self):
        """同标题在 3s 去重窗口内返回 False。"""
        svc = NotifyService(None)
        assert svc._check_dedup("dup_title") is True
        assert svc._check_dedup("dup_title") is False

    def test_boundary_different_title_within_window_returns_true(self):
        """不同标题在 3s 窗口内不触发去重。"""
        svc = NotifyService(None)
        assert svc._check_dedup("title_a") is True
        assert svc._check_dedup("title_b") is True

    def test_boundary_null_tray_show_returns_silently(self):
        """tray=None 时 show 静默返回不崩溃。"""
        svc = NotifyService(None)
        svc._enabled = True
        svc.show("T", "M")  # 不抛异常

    def test_state_dedup_window_expires(self):
        """去重窗口过期后同标题可再次发送。"""
        svc = NotifyService(None)
        assert svc._check_dedup("expire_test") is True
        # 模拟时间前进 4 秒（超过 3s 窗口）
        svc._last["expire_test"] = time.monotonic() - 4.0
        assert svc._check_dedup("expire_test") is True


class TestAggregatorPath:
    """聚合器路径 — 覆盖 auto_pause_enabled=True 分支。"""

    def test_show_via_aggregator_when_auto_pause_enabled(self):
        """auto_pause_enabled=True 时走 should_show 聚合路径。"""
        mock_tray = MagicMock()
        svc = NotifyService(mock_tray)
        svc._enabled = True
        mock_agg = MagicMock()
        mock_agg.auto_pause_enabled = True
        with patch.object(svc, "_get_aggregator", return_value=mock_agg):
            svc.show("Agg Title", "Agg Body", 5000)
            mock_agg.should_show.assert_called_once()

    def test_show_warning_via_aggregator_when_auto_pause_enabled(self):
        """show_warning 聚合器路径正确调用 should_show。"""
        mock_tray = MagicMock()
        svc = NotifyService(mock_tray)
        svc._enabled = True
        mock_agg = MagicMock()
        mock_agg.auto_pause_enabled = True
        with patch.object(svc, "_get_aggregator", return_value=mock_agg):
            svc.show_warning("Warn Agg", "Warn Body", 3000)
            mock_agg.should_show.assert_called_once()
