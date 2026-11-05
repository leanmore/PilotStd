"""UI 线程优雅停止契约（G-029 同步测试）：先断信号、stop、requestInterruption、wait。"""

from pilotstd.ui.qt_lifecycle import stop_worker_gracefully


class _Signal:
    def __init__(self):
        self.disconnected = False

    def disconnect(self):
        self.disconnected = True


class _FakeWorker:
    def __init__(self, running=True):
        self.running = running
        self.stopped = False
        self.interrupted = False
        self.waited = 0

    def stop(self):
        self.stopped = True

    def requestInterruption(self):
        self.interrupted = True

    def isRunning(self):
        return self.running

    def isFinished(self):
        return not self.running

    def wait(self, timeout_ms):
        self.waited = timeout_ms
        self.running = False
        return True


def test_stop_worker_gracefully_order_and_flags():
    worker = _FakeWorker(running=True)
    signal = _Signal()
    assert stop_worker_gracefully(worker, signals=(signal,), timeout_ms=100) is True
    assert signal.disconnected is True
    assert worker.stopped is True
    assert worker.interrupted is True
    assert worker.waited == 100
    assert worker.running is False


def test_stop_worker_none_is_noop():
    assert stop_worker_gracefully(None) is True
