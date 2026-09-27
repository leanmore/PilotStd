"""测试 wait_for_worker_and_ui — 覆盖核心场景 + 解析/哨兵契约。"""

import time

import pytest

from tests.gui.helpers import wait_for_worker_and_ui
from tests.gui.helpers.predicates import worker_done


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


def test_worker_none_fails_loudly(fake_qtbot):
    """Worker 为 None（尚未创建）→ 必须**断言失败**，不得静默跳过线程等待。

    旧契约是"worker 为 None 就只等 UI 条件、直接通过"——正是它把 53 处等待变成空操作，
    掩盖了 QThread 生命周期崩溃（CI test-gui-coverage 134）。
    """
    window = _FakeWindow(worker=None)
    with pytest.raises(AssertionError, match="为 None（尚未创建）"):
        wait_for_worker_and_ui(
            fake_qtbot, window, "_test_worker",
            ui_predicate=lambda: True,
            timeout=500,
        )


def test_worker_attribute_not_found_fails_loudly(fake_qtbot):
    """属性名写错/结构变了（窗口与 _core.<handler> 都找不到）→ 断言失败，不再当作 None 静默跳过。"""
    window = _FakeWindow(worker=_FakeWorker(running_duration=0.01))
    with pytest.raises(AssertionError, match="找不到 worker '_no_such_worker'"):
        wait_for_worker_and_ui(
            fake_qtbot, window, "_no_such_worker",
            ui_predicate=lambda: True,
            timeout=500,
        )


def test_worker_object_may_be_passed_directly(fake_qtbot):
    """worker 也可直接传对象（helper 支持"对象 or 属性名"两种写法）。"""
    worker = _FakeWorker(running_duration=0.01)
    window = _FakeWindow(worker=worker)
    wait_for_worker_and_ui(
        fake_qtbot, window, worker,
        ui_predicate=lambda: True,
        timeout=1000,
    )


def test_worker_done_sentinel_actually_waits(fake_qtbot):
    """`ui_predicate=worker_done` 必须真的等到 worker 结束（旧实现恒返回 True，等于不等）。"""
    window = _FakeWindow(worker=_FakeWorker(running_duration=0.3))
    with pytest.raises(AssertionError, match="did not finish within 100ms"):
        wait_for_worker_and_ui(
            fake_qtbot, window, "_test_worker",
            ui_predicate=worker_done,
            timeout=100,  # 假 worker 要 300ms 才结束 → 必须超时
        )


def test_worker_done_sentinel_is_not_callable():
    """哨兵对象刻意不可调用：误当普通谓词传给 waitUntil 会立刻 TypeError，而不是恒为真。"""
    assert not callable(worker_done)
    assert repr(worker_done) == "worker_done"


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
