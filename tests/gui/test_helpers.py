"""测试 wait_for_worker_and_ui — 覆盖 6 种核心场景。"""

import time

import pytest

from tests.gui.helpers import wait_for_worker_and_ui


class _FakeWorker:
    """模拟 QThread Worker。"""

    def __init__(self, running_duration: float = 0.0):
        self._running_duration = running_duration
        self._start_time: float | None = None

    def isRunning(self) -> bool:
        if self._start_time is None:
            self._start_time = time.monotonic()
            return True
        return (time.monotonic() - self._start_time) < self._running_duration


class _FakeWindow:
    def __init__(self, worker=None):
        self._test_worker = worker


@pytest.fixture
def fake_qtbot(qtbot):
    """复用真实 qtbot，确保 waitUntil 行为一致。"""
    return qtbot


def test_worker_finishes_and_ui_met(fake_qtbot):
    """正常场景：Worker 快速结束 + UI 条件立即满足。"""
    window = _FakeWindow(worker=_FakeWorker(running_duration=0.01))
    wait_for_worker_and_ui(
        fake_qtbot, window, "_test_worker",
        ui_predicate=lambda: True,
        timeout=1000,
    )


def test_worker_timeout(fake_qtbot):
    """Worker 超时未完成。"""
    window = _FakeWindow(worker=_FakeWorker(running_duration=10.0))
    with pytest.raises(AssertionError, match="did not finish within 200ms"):
        wait_for_worker_and_ui(
            fake_qtbot, window, "_test_worker",
            ui_predicate=lambda: True,
            timeout=200,
        )


def test_ui_condition_timeout(fake_qtbot):
    """Worker 完成但 UI 条件始终不满足。"""
    window = _FakeWindow(worker=_FakeWorker(running_duration=0.01))
    with pytest.raises(AssertionError, match="finished but UI condition not met"):
        wait_for_worker_and_ui(
            fake_qtbot, window, "_test_worker",
            ui_predicate=lambda: False,
            timeout=200,
        )


def test_worker_none_but_ui_met(fake_qtbot):
    """Worker 不存在但 UI 条件满足 → 应正常通过。"""
    window = _FakeWindow(worker=None)
    wait_for_worker_and_ui(
        fake_qtbot, window, "_test_worker",
        ui_predicate=lambda: True,
        timeout=500,
    )


def test_worker_none_and_ui_timeout(fake_qtbot):
    """Worker 不存在且 UI 条件不满足 → 消息应包含 'does not exist'。"""
    window = _FakeWindow(worker=None)
    with pytest.raises(AssertionError, match="does not exist and UI condition"):
        wait_for_worker_and_ui(
            fake_qtbot, window, "_test_worker",
            ui_predicate=lambda: False,
            timeout=200,
        )


def test_custom_message_override(fake_qtbot):
    """自定义 message 应覆盖默认消息。"""
    window = _FakeWindow(worker=_FakeWorker(running_duration=0.01))
    custom_msg = "Custom: table never populated"
    with pytest.raises(AssertionError, match=custom_msg):
        wait_for_worker_and_ui(
            fake_qtbot, window, "_test_worker",
            ui_predicate=lambda: False,
            timeout=200,
            message=custom_msg,
        )
