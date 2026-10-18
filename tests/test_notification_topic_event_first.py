"""D-3：通知主题判定改为「事件键优先、标题/关键词兜底」（后端作业，不 import PyQt）。"""

from __future__ import annotations

from pilotstd.core.notification_aggregator import NotificationAggregator


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

