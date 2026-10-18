"""D-3：NotifyService.show_event 把 event_type 交给主题判定（GUI 作业，notify 依赖 PyQt6）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("PyQt6")


def test_show_event_passes_event_type_to_topic(monkeypatch) -> None:
    from pilotstd.platform.notify import NotifyService

    service = object.__new__(NotifyService)
    service._enabled = True
    service._tray = object()
    fake_agg = MagicMock()
    fake_agg.topic_of.return_value = "done"
    monkeypatch.setattr(service, "_get_aggregator", lambda: fake_agg)
    monkeypatch.setattr(service, "_check_event_window", lambda topic: True)
    monkeypatch.setattr(service, "show", lambda *a, **k: None)

    service.show_event("标题", "正文", "info", event_type="scan_complete")

    fake_agg.topic_of.assert_called_once_with("标题", "正文", "scan_complete")
