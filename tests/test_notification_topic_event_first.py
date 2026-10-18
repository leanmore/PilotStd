"""D-3：通知主题判定改为「事件键优先、标题/关键词兜底」。"""

from __future__ import annotations

from unittest.mock import MagicMock

from pilotstd.core.notification_aggregator import NotificationAggregator
from pilotstd.platform.notify import NotifyService


def _aggregator() -> NotificationAggregator:
    return object.__new__(NotificationAggregator)


def test_event_key_first_ignores_title_language() -> None:
    agg = _aggregator()
    # 标题故意与主题无关；事件键 scan_complete → done
    assert agg.topic_of("completely unrelated title", "", "scan_complete") == "done"
    assert agg.topic_of("完全无关的标题", "", "download_complete") == "done"


def test_unknown_event_falls_back_to_title_keywords() -> None:
    agg = _aggregator()
    title = "backup 完成"
    assert agg.topic_of(title, "", "no_such_event") == agg.topic_of(title, "")


def test_without_event_behavior_unchanged() -> None:
    agg = _aggregator()
    for title in ("扫描完成", "下载完成", "归档完成", "some custom title"):
        assert agg.topic_of(title, "") == agg._extract_topic(title, "")


def test_show_event_passes_event_type_to_topic(monkeypatch) -> None:
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
