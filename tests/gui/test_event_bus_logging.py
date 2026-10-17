"""EventBus 取消订阅的失败可见性（体检 D-8 第 8 批，GUI 作业）。

`unsubscribe` 对未注册回调会抛 ValueError，原实现 pass；现记 debug。
"""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("PyQt6")


def test_unsubscribe_missing_callback_logs(qapp, caplog) -> None:
    from pilotstd.ui.core.event_bus import EventBus

    bus = EventBus()
    callback = lambda: None  # noqa: E731
    bus.subscribe("some_event", callback, weak=False)
    bus._subscribers["some_event"].clear()  # 模拟事件仍在、回调已被移除
    with caplog.at_level(logging.DEBUG, logger="pilotstd.ui.core.event_bus"):
        bus.unsubscribe("some_event", callback)
    assert "unsubscribe: callback not registered" in caplog.text
