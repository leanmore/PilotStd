# tests/gui/test_event_bus_integration.py
"""EventBus 集成测试 — 验证事件路由、线程安全、单例隔离。

测试策略：
- 每个测试前 reset() 清空单例状态
- 覆盖 subscribe/publish/unsubscribe 基本流程
- 覆盖跨线程发布
- 覆盖 auto pipeline 事件实际触发
"""

from __future__ import annotations

import os
import shutil
import threading
import time

import pytest
from PyQt6.QtCore import QThread, pyqtSignal

from pilotstd.ui.core.event_bus import EventBus

# pytest-xdist 下将本模块所有 EventBus 测试固定到同一 worker 串行执行，
# 避免 EventBus 单例跨 worker 并发访问（Windows CI 曾现 Access Violation）
pytestmark = pytest.mark.xdist_group("event_bus_thread_safety")


@pytest.fixture(autouse=True)
def _reset_event_bus():
    """每个测试前重置 EventBus 单例，防止测试间污染。

    teardown 先等待非主线程退出（上限 2s），再 reset()——
    避免 reset 访问未完全退出的后台线程持有的 Qt 对象（Windows Access Violation 根因）。
    """
    EventBus.reset()
    yield
    deadline = time.monotonic() + 2.0
    while any(
        t.is_alive() for t in threading.enumerate() if t is not threading.main_thread()
    ):
        if time.monotonic() > deadline:
            break
        time.sleep(0.05)
    EventBus.reset()


@pytest.fixture
def bus() -> EventBus:
    return EventBus.instance()


# ═══════════════════════════════════════════════════════════════════
# 单例
# ═══════════════════════════════════════════════════════════════════


class TestSingleton:
    def test_same_instance(self):
        a = EventBus.instance()
        b = EventBus.instance()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = EventBus.instance()
        EventBus.reset()
        b = EventBus.instance()
        assert a is not b


# ═══════════════════════════════════════════════════════════════════
# 订阅/发布
# ═══════════════════════════════════════════════════════════════════


class TestSubscribePublish:
    def test_basic(self, bus, qtbot):
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test.event", handler)
        bus.publish("test.event", {"key": "value"})

        # QueuedConnection 需要事件循环处理
        qtbot.waitUntil(lambda: len(received) > 0, timeout=2000)
        assert len(received) == 1
        assert received[0] == {"key": "value"}

    def test_multiple_subscribers(self, bus, qtbot):
        results = []

        def h1(data):
            results.append(f"h1:{data}")

        def h2(data):
            results.append(f"h2:{data}")

        bus.subscribe("multi.event", h1)
        bus.subscribe("multi.event", h2)
        bus.publish("multi.event", "data")

        qtbot.waitUntil(lambda: len(results) == 2, timeout=2000)
        assert "h1:data" in results
        assert "h2:data" in results

    def test_unsubscribe(self, bus, qtbot):
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test.unsub", handler)
        bus.publish("test.unsub", 1)
        qtbot.waitUntil(lambda: len(received) == 1, timeout=2000)

        bus.unsubscribe("test.unsub", handler)
        bus.publish("test.unsub", 2)
        # 给事件循环一点时间处理（如果错误触发）
        time.sleep(0.1)
        assert len(received) == 1  # 不应收到第二条

    def test_no_subscribers_no_error(self, bus):
        """发布到无人订阅的事件不应崩溃。"""
        bus.publish("no.such.event", {})  # 不抛异常即可

    def test_callback_exception_handled(self, bus, qtbot):
        """回调内抛异常不应影响其他订阅者。"""
        results = []

        def bad_handler(data):
            raise RuntimeError("模拟异常")

        def good_handler(data):
            results.append("ok")

        bus.subscribe("error.event", bad_handler)
        bus.subscribe("error.event", good_handler)
        bus.publish("error.event", {})

        qtbot.waitUntil(lambda: len(results) == 1, timeout=2000)
        assert results == ["ok"]


# ═══════════════════════════════════════════════════════════════════
# 线程安全
# ═══════════════════════════════════════════════════════════════════


class _TestWorker(QThread):
    progress = pyqtSignal(int)

    def run(self):
        bus = EventBus.instance()
        for i in range(3):
            bus.publish("worker.progress", {"pct": i * 33})


class TestThreadSafety:
    def test_publish_from_worker_thread(self, bus, qtbot):
        """从 Worker 线程发布事件，主线程回调接收。"""
        results = []

        def handler(data):
            results.append(data)

        bus.subscribe("worker.progress", handler)

        worker = _TestWorker()
        worker.start()

        qtbot.waitUntil(lambda: len(results) == 3, timeout=5000)
        worker.wait()
        assert len(results) == 3
        assert results[0] == {"pct": 0}

    def test_concurrent_subscribe(self, bus):
        """并发订阅不应崩溃。"""
        errors = []

        def subscriber(prefix):
            try:
                for i in range(100):
                    bus.subscribe("concurrent.event", lambda d, p=prefix: None)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=subscriber, args=(f"t{i}",)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════
# 弱引用清理
# ═══════════════════════════════════════════════════════════════════


class TestWeakRef:
    def test_weak_subscriber_cleaned(self, bus, qtbot):
        """对象销毁后弱引用回调不再触发。"""
        results = []

        class Subscriber:
            def handler(self, data):
                results.append(data)

        sub = Subscriber()
        bus.subscribe("weak.event", sub.handler, weak=True)
        bus.publish("weak.event", 1)
        qtbot.waitUntil(lambda: len(results) == 1, timeout=2000)

        del sub  # 销毁对象
        bus.publish("weak.event", 2)
        time.sleep(0.2)  # 等待事件处理
        # 弱引用清理后不应触发
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════
# Auto pipeline 事件集成
# ═══════════════════════════════════════════════════════════════════


def _copy_fixtures(src_dir: str, dst_dir: str):
    os.makedirs(dst_dir, exist_ok=True)
    for name in os.listdir(src_dir):
        src = os.path.join(src_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, name))


@pytest.mark.e2e
def test_auto_pipeline_emits_events(window, test_data_dir, qtbot, tmp_path):
    """验证 auto pipeline 实际发出 stage 和 finished 事件。"""
    bus = EventBus.instance()

    source_dir = tmp_path / "scan_source"
    _copy_fixtures(test_data_dir, str(source_dir))

    lib_dir = tmp_path / "library"
    dl_dir = tmp_path / "downloads"
    lib_dir.mkdir(exist_ok=True)
    dl_dir.mkdir(exist_ok=True)

    handler = window._core.auto
    window._mgr.download_engine._save_root = str(dl_dir)
    window._config.set("storage.root_dir", str(lib_dir))
    window._config.save()

    stages = []
    finished = []

    def on_stage(data):
        stages.append(data["stage"])

    def on_finished(data):
        finished.append(data)

    bus.subscribe("auto.stage.scan", on_stage)
    bus.subscribe("auto.stage.query", on_stage)
    bus.subscribe("auto.stage.download", on_stage)
    bus.subscribe("auto.stage.archive", on_stage)
    bus.subscribe("auto.stage.done", on_stage)
    bus.subscribe("auto.pipeline.finished", on_finished)

    handler.start_auto_pipeline(str(source_dir))

    worker = handler._auto_worker
    assert worker is not None

    with qtbot.waitSignal(worker.finished_signal, timeout=60000):
        pass

    qtbot.waitUntil(lambda: len(finished) > 0, timeout=2000)
    assert len(stages) > 0, f"应至少触发一个 stage 事件，实际: {stages}"
    assert "scan" in stages, f"应包含 scan 阶段，实际: {stages}"
    assert "done" in stages, f"应包含 done 阶段，实际: {stages}"
    assert len(finished) == 1
    assert "scan" in finished[0]


# ═══════════════════════════════════════════════════════════════════
# Handler 事件发布验证
# ═══════════════════════════════════════════════════════════════════


class _FakeWorker(QThread):
    progress = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        self.progress.emit(50)
        self.progress.emit(100)
        self.finished_signal.emit()


@pytest.mark.e2e
def test_scan_handler_emits_events(window, test_data_dir, qtbot, tmp_path):
    """扫描 Handler 应发布 scan.batch_ready、scan.finished 事件。"""
    _copy_fixtures(test_data_dir, str(tmp_path))
    bus = EventBus.instance()

    events = []
    bus.subscribe("scan.batch_ready", lambda d: events.append(("batch", d)))
    bus.subscribe("scan.finished", lambda d: events.append(("finished", d)))

    handler = window._core.scan
    handler.run_scan(str(tmp_path))

    worker = handler._scan_worker
    if worker is not None:
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=30000)

    # 等待 finished 事件（finished 后于 batch 到达，等 finished 即隐含 batch 已到）
    qtbot.waitUntil(lambda: any(e[0] == "finished" for e in events), timeout=3000)
    assert any(e[0] == "batch" for e in events), f"应收到 batch 事件: {events}"
    assert any(e[0] == "finished" for e in events), f"应收到 finished 事件: {events}"


@pytest.mark.e2e
def test_scan_handler_migration_no_regression(window, test_data_dir, qtbot, tmp_path):
    """迁移后：run_scan 行为不变，表格正常填充。"""
    _copy_fixtures(test_data_dir, str(tmp_path))

    handler = window._core.scan
    handler.run_scan(str(tmp_path))

    worker = handler._scan_worker
    if worker is not None:
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=30000)

    table = window.work_table
    assert table.rowCount() > 0, "扫描后表格应有数据"

