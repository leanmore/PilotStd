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
from PyQt6.QtCore import QCoreApplication, QThread, QThreadPool, pyqtSignal

from pilotstd.ui.core.event_bus import EventBus

# pytest-xdist 下将本模块所有 EventBus 测试固定到同一 worker 串行执行，
# 避免 EventBus 单例跨 worker 并发访问（Windows CI 曾现 Access Violation）
pytestmark = pytest.mark.xdist_group("event_bus_thread_safety")


def _wait_for_threads(timeout: float) -> bool:
    """等待非主线程退出并等 Qt 全局线程池收敛；返回是否已"静止"。

    `threading.enumerate()` 只看得到 Python 线程，看不到 Qt 内部线程/QThreadPool，
    故补一次 `QThreadPool.waitForDone()`——否则可能在 Qt 侧仍有 in-flight 任务时 reset。
    """
    deadline = time.monotonic() + timeout
    while any(
        t.is_alive() for t in threading.enumerate() if t is not threading.main_thread()
    ):
        if time.monotonic() > deadline:
            break
        time.sleep(0.05)
    QThreadPool.globalInstance().waitForDone(2000)
    return not any(
        t.is_alive() for t in threading.enumerate() if t is not threading.main_thread()
    )


@pytest.fixture(autouse=True)
def _reset_event_bus():
    """每个测试前重置 EventBus 单例，防止测试间污染。

    teardown 先等待非主线程退出（上限 5s）并等 Qt 线程池收敛，再 reset()——
    避免 reset 访问未完全退出的后台线程持有的 Qt 对象（Windows Access Violation 根因）。

    到期仍未静止时**不再 reset**：此刻 `cls._instance = None` 会销毁那个 QObject，
    而其它线程可能仍在 publish() / 排队 deliver 中引用它（use-after-free）。
    CI 的两次 access violation（run 36218068788 / 36293074107）都落在这一行。
    此时把清理留给下一次 setup 的 reset()——那时残留线程通常已结束，不再处于竞态窗口。
    """
    EventBus.reset()
    yield
    if not _wait_for_threads(5.0):
        return
    app = QCoreApplication.instance()
    if app is not None:  # 排空主线程事件队列里剩余的 deliver，避免 reset 后仍被投递
        app.processEvents()
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

    def test_reset_keeps_instance_and_clears_state(self):
        """reset() 契约（R12-5 修正）：**同一实例 + 状态清零**，不再返回新对象。

        旧契约（`a is not b`）正是 use-after-free 缺陷本身——销毁 QObject 时其它线程可能
        仍持有引用（R4 探针实测 0xC0000005）。新契约下对象恒有效，重置等价于「清空到初始态」。
        """
        a = EventBus.instance()
        a.subscribe("scan.finished", lambda _d: None)
        EventBus.reset()
        b = EventBus.instance()
        assert b is a, "reset() 后必须复用同一实例（保活，不再销毁 QObject）"
        assert a._subscribers == {}, "reset() 必须把订阅者表清空至初始态"
        assert a._weak_subscribers == {}


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

    # 扫描结果经 QueuedConnection 投递到主线程才填表；只等 worker.isRunning() 为假
    # 会在槽尚未执行时提前返回（waitUntil 首判为真则不跑事件循环）→ 断言到 0 行。
    table = window.work_table
    qtbot.waitUntil(lambda: table.rowCount() > 0, timeout=30000)

    assert table.rowCount() > 0, "扫描后表格应有数据"


# ═══════════════════════════════════════════════════════════════════
# reset() 保活单例协议（R12-4 静止协议 → R12-5 保活单例）
# ═══════════════════════════════════════════════════════════════════


class TestResetQuiescenceProtocol:
    """锁定 reset() 的协议：关门 → 清状态（世代 +1）→ 有界排空 → 复位；**实例永不析构**。"""

    def test_resetting_flag_is_cleared_after_reset(self):
        EventBus.instance()
        EventBus.reset()
        assert EventBus._resetting is False, "reset() 结束后必须复位门闸，否则后续 publish 永久失效"

    def test_publish_after_reset_with_stale_reference_is_discarded(self):
        """reset() 前排队的调用（含经旧引用发布的）不得在 reset 后触达回调。

        保活单例下不再有“退役实例”，隔离改由**世代号**保证：reset 递增世代，
        陈旧事件在 deliver 时被丢弃。
        """
        old = EventBus.instance()
        received: list[object] = []
        old.subscribe("scan.finished", received.append)
        # 先让一次真实投递排进队列，再立刻 reset —— 该事件属于旧世代
        old.publish("scan.finished", {"n": 1})
        EventBus.reset()

        received.clear()
        # reset 之后重新订阅；旧世代事件若漏网就会误触这个新回调
        old.subscribe("scan.finished", received.append)
        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()
        assert received == [], "reset 之前入队的陈旧事件必须被丢弃（世代号门闸）"

        # 新世代的事件照常投递（实例仍然可用）
        old.publish("scan.finished", {"n": 2})
        if app is not None:
            app.processEvents()
        assert received == [{"n": 2}], "reset 之后的新事件必须正常投递（实例保活且可用）"

    def test_publish_during_reset_window_is_noop(self):
        """reset() 窗口内（_resetting=True）的 publish 必须不入队、不抛异常。"""
        bus = EventBus.instance()
        received: list[object] = []
        bus.subscribe("scan.finished", received.append)
        EventBus._resetting = True
        try:
            bus.publish("scan.finished", {"n": 2})  # 必须 no-op
        finally:
            EventBus._resetting = False
        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()
        assert received == [], "静止窗口内不得入队任何 deliver"

    def test_subscribe_during_reset_window_is_noop(self):
        bus = EventBus.instance()
        EventBus._resetting = True
        try:
            bus.subscribe("scan.finished", lambda _d: None)
        finally:
            EventBus._resetting = False
        assert "scan.finished" not in bus._subscribers, "静止窗口内不得写入订阅状态"

    def test_reset_is_idempotent_and_keeps_object_alive(self):
        """连续 reset 不抛异常、不换对象；实例始终可继续使用。"""
        a = EventBus.instance()
        a.subscribe("scan.finished", lambda _d: None)
        for _ in range(3):
            EventBus.reset()
            assert EventBus.instance() is a, "reset() 不得替换实例（保活）"
        assert a._subscribers == {}

    def test_publisher_thread_during_reset_does_not_raise(self):
        """跨线程 teardown 场景冒烟：一边多线程 publish，一边 reset——不得抛异常。"""
        errors: list[BaseException] = []
        stop = threading.Event()

        def publisher() -> None:
            bus = EventBus.instance()
            while not stop.is_set():
                try:
                    bus.publish("scan.progress", {"i": 1})
                except BaseException as exc:  # noqa: BLE001 - 测试需捕获一切异常用于断言
                    errors.append(exc)
                    return

        threads = [threading.Thread(target=publisher, daemon=True) for _ in range(3)]
        for t in threads:
            t.start()
        try:
            for _ in range(5):
                EventBus.reset()
        finally:
            stop.set()
            for t in threads:
                t.join(timeout=5.0)
        assert errors == [], f"reset 期间跨线程 publish 不得抛异常: {errors}"


