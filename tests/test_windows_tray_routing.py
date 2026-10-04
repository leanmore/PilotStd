"""W2 按端分流：桌面托盘事件出口（接线开关 + 线程桥路由）。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# 环境守卫（对齐既有惯例，见 tests/unit/core/test_status.py:171 与
# tests/test_notification_aggregator_topic_i18n.py:326）：本文件全部用例都构造
# `_TrayEventBridge` / `NotifyService`，二者顶层依赖 PyQt6；`test-backend` 作业
# 不安装 GUI 依赖 ⇒ 模块级跳过，本地与 CI 的 GUI 作业中仍会真实执行。
pytest.importorskip("PyQt6", reason="桌面托盘路由需 PyQt6，后端测试作业不含 GUI 依赖")


def _stub_window(*, tray: object | None = object(), switch: bool = True):
    """最小窗口替身：只提供 `_wire_tray_event_sink` 需要的三样（配置/托盘/管理器）。"""
    fake_notification_mgr = SimpleNamespace(set_local_sink=MagicMock())
    return SimpleNamespace(
        _config=SimpleNamespace(
            get=lambda key, default=None: (
                switch if key == "notification.windows_tray_events" else default
            )
        ),
        _tray=tray,
        _mgr=SimpleNamespace(notification_mgr=fake_notification_mgr),
    )


def test_wire_sets_sink_when_enabled():
    """开关开启且托盘存在：注入本地信号出口（Docker 端不调用本方法 ⇒ 不注入）。

    桥本身用替身：窗口替身是 SimpleNamespace（非 QObject），不能作为 Qt 子对象父级；
    桥的自身行为由 `test_bridge_routes_by_level` 覆盖。
    """
    from pilotstd.ui.main_window.parts import _ui_setup_ops

    window = _stub_window()
    bridge = SimpleNamespace(tray_event_occurred=SimpleNamespace(emit=MagicMock()))
    with patch.object(_ui_setup_ops, "_TrayEventBridge", return_value=bridge):
        _ui_setup_ops._wire_tray_event_sink(window)

    window._mgr.notification_mgr.set_local_sink.assert_called_once()
    sink = window._mgr.notification_mgr.set_local_sink.call_args.args[0]
    sink(SimpleNamespace(event_type="scan_complete", title="扫描完成", body="共 3 条", level="info"))
    bridge.tray_event_occurred.emit.assert_called_once_with("scan_complete", "扫描完成", "共 3 条", "info")


def test_wire_skips_when_switch_off():
    """分流开关关闭：不注入（等价于回退到"本端无可见信号"）。"""
    from pilotstd.ui.main_window.parts._ui_setup_ops import _wire_tray_event_sink

    window = _stub_window(switch=False)
    _wire_tray_event_sink(window)
    window._mgr.notification_mgr.set_local_sink.assert_not_called()


def test_wire_skips_without_tray():
    """无托盘（如无 GUI 环境/测试替身）：不注入，避免拉起 GUI 依赖。"""
    from pilotstd.ui.main_window.parts._ui_setup_ops import _wire_tray_event_sink

    window = _stub_window(tray=None)
    _wire_tray_event_sink(window)
    window._mgr.notification_mgr.set_local_sink.assert_not_called()


def test_bridge_routes_by_level():
    """线程桥按级别分流（**关闭节流**时）：warning/error → show_warning，其余 → show。

    节流开启时统一走 `show_event`（由它内部按级别再分派），见
    `test_bridge_uses_throttled_entry_when_enabled`。
    """
    from pilotstd.ui.main_window.parts._ui_setup_ops import _TrayEventBridge

    service = MagicMock()
    with patch("pilotstd.platform.notify.NotifyService.get", return_value=service):
        bridge = _TrayEventBridge()
        bridge.throttle = False
        bridge.tray_event_occurred.emit("scan_complete", "扫描完成", "共 3 条", "info")
        bridge.tray_event_occurred.emit("download_failed", "下载失败", "连接超时", "warning")

    service.show.assert_called_once_with("扫描完成", "共 3 条")
    service.show_warning.assert_called_once_with("下载失败", "连接超时")


def test_bridge_uses_throttled_entry_when_enabled():
    """W3：节流开（默认）时走 `show_event`（长阶段 60 秒/主题由它负责）。"""
    from pilotstd.ui.main_window.parts._ui_setup_ops import _TrayEventBridge

    service = MagicMock()
    with patch("pilotstd.platform.notify.NotifyService.get", return_value=service):
        bridge = _TrayEventBridge()
        bridge.throttle = True
        bridge.tray_event_occurred.emit("scan_complete", "扫描完成", "共 3 条", "info")

    service.show_event.assert_called_once_with("扫描完成", "共 3 条", "info")
    service.show.assert_not_called()


def test_bridge_falls_back_when_throttle_off():
    """W3 回退：关闭节流后回到不节流的 show/show_warning（与 W2 初版一致）。"""
    from pilotstd.ui.main_window.parts._ui_setup_ops import _TrayEventBridge

    service = MagicMock()
    with patch("pilotstd.platform.notify.NotifyService.get", return_value=service):
        bridge = _TrayEventBridge()
        bridge.throttle = False
        bridge.tray_event_occurred.emit("scan_complete", "扫描完成", "共 3 条", "info")
        bridge.tray_event_occurred.emit("download_failed", "下载失败", "超时", "warning")

    service.show_event.assert_not_called()
    service.show.assert_called_once_with("扫描完成", "共 3 条")
    service.show_warning.assert_called_once_with("下载失败", "超时")
