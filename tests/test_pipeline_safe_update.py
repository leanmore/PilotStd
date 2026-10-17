"""管道进度写入封装与可信 IP 通知回调的吞错治理（体检 D-11）。

原实现：四个端点各自 `except Exception: pass`，写进度失败时前端进度条停在中间态
且无痕迹；`wechat_ip._notify` 的回调异常同样被静默丢弃。
"""

from __future__ import annotations

import logging


def test_safe_update_step_passes_arguments() -> None:
    from docker.api._pipeline import safe_update_step

    class Store:
        def __init__(self) -> None:
            self.calls = []

        def update_step(self, run_id, step, status, percent, **kwargs) -> None:
            self.calls.append((run_id, step, status, percent, kwargs))

    store = Store()
    safe_update_step(store, "run-1", "query", "running", 20, step_results={"count": 3})
    assert store.calls == [("run-1", "query", "running", 20, {"step_results": {"count": 3}})]


def test_safe_update_step_logs_and_does_not_raise(caplog) -> None:
    from docker.api._pipeline import safe_update_step

    class BrokenStore:
        def update_step(self, *args, **kwargs) -> None:
            raise RuntimeError("pipeline store broken")

    with caplog.at_level(logging.INFO, logger="docker.api._pipeline"):
        safe_update_step(BrokenStore(), "run-2", "archive", "running", 80)

    assert "pipeline update skipped" in caplog.text
    assert "run-2" in caplog.text
    assert "archive" in caplog.text


# ── wechat_ip 通知回调 ──────────────────────────────────────────────


def test_notify_logs_warning_when_callback_raises(caplog) -> None:
    from pilotstd.wechat_ip import scheduler as wechat_scheduler

    def broken_cb(title, body, status):
        raise RuntimeError("notify boom")

    with caplog.at_level(logging.WARNING, logger="pilotstd.wechat_ip.scheduler"):
        wechat_scheduler._notify(broken_cb, "t", "b", "ok")  # 不得抛出

    assert "wechat_ip notify callback failed" in caplog.text
    assert "notify boom" in caplog.text


def test_notify_passes_status_to_callback() -> None:
    from pilotstd.wechat_ip import scheduler as wechat_scheduler

    calls = []
    wechat_scheduler._notify(lambda *args: calls.append(args), "t", "b", "failed")
    assert calls == [("t", "b", "failed")]


def test_notify_none_callback_is_noop() -> None:
    from pilotstd.wechat_ip import scheduler as wechat_scheduler

    wechat_scheduler._notify(None, "t", "b")  # 不应抛异常
