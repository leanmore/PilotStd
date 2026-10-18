"""D-3：托盘桥必须把 event_type 传给 NotifyService.show_event（事件键优先）。"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


def test_bridge_passes_event_type(qapp, monkeypatch) -> None:
    from types import SimpleNamespace

    from pilotstd.ui.main_window.parts import _ui_setup_ops as ops

    recorded: dict[str, str] = {}

    class FakeService:
        def show_event(self, title, message, level, event_type=""):
            recorded.update(title=title, message=message, level=level, event_type=event_type)

    monkeypatch.setattr(
        "pilotstd.platform.notify.NotifyService",
        SimpleNamespace(get=lambda: FakeService()),
    )

    bridge = ops._TrayEventBridge()
    bridge._show("scan_complete", "扫描完成", "正文", "info")

    assert recorded == {
        "title": "扫描完成",
        "message": "正文",
        "level": "info",
        "event_type": "scan_complete",
    }
