# tests/gui/test_worker_lifecycle.py
"""回归测试：取消 / 销毁后，迟到的后台信号不得访问已删除的 Qt 对象。

CI 事故（test-gui-coverage，2026-09-21）：
`test_manual_workflow.py::test_buttons_enabled_after_cancel` 点击取消后控件已被
Qt 析构，QueryWorker 的排队信号仍被投递，槽函数抛
`RuntimeError: wrapped C/C++ object of type QTableWidget/QTimer has been deleted`。

修复分三层，本文件逐层守卫：
  1. 取消时**先断开** worker 全部业务信号，再协作式停线程（pilotstd/ui/qt_lifecycle.py）；
  2. 槽函数入口用 `sip.isdeleted` 兜底（工作表格 / 进度管道）；
  3. 测试取消后必须等线程真正结束并排空事件循环，再断言。
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6 import sip as _sip
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tests.gui.helpers import wait_for_worker_and_ui  # noqa: E402


def _scan_and_query(window, qtbot, test_data_dir: str, prefix: str) -> str:
    """扫描 fixture → 发起查询 → 返回临时目录（调用方负责清理）。"""
    tmp = tempfile.mkdtemp(prefix=prefix)
    for name in os.listdir(test_data_dir):
        src = os.path.join(test_data_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, tmp)

    window._suppress_dialogs = True
    window._run_scan(tmp)
    wait_for_worker_and_ui(
        qtbot, window, "_scan_worker",
        ui_predicate=lambda: len(window._parsed_results) > 0,
    )
    window._on_query()
    return tmp


def test_cancel_disconnects_worker_signals(window, test_data_dir, qtbot, monkeypatch):
    """取消后 worker 的业务信号必须已断开：再次发射也不会触碰工作表格。"""
    tmp = _scan_and_query(window, qtbot, test_data_dir, "pilotstd_lifecycle_disc_")
    try:
        handler = window._core.query
        worker = handler._query_worker
        assert worker is not None, "on_query 应创建 QueryWorker"

        # 等待器挂在取消之前：QThread 内建 finished 不受业务信号断开影响
        waiter = qtbot.waitSignal(worker.finished, timeout=3000) if worker.isRunning() else None
        window._on_cancel()
        if waiter is not None:
            waiter.wait()
        qtbot.wait(50)  # 排空事件循环，让排队中的槽调用先跑完
        assert not worker.isRunning(), "取消后查询线程应已结束"

        # 哨兵表格：断连成功则它永远不会被访问（等价于"不会碰到已析构控件"）
        accessed: list[str] = []

        class _ProbeTable:
            """记录被访问次数的假表格适配器。"""

            def get_work_table(self):
                accessed.append("get_work_table")
                return None

        monkeypatch.setattr(handler._deps, "table", _ProbeTable())

        worker.result_ready.emit(0, object())
        worker.batch_ready.emit([(0, object())])
        worker.progress.emit(50)
        worker.finished_signal.emit([])
        worker.error.emit("迟到错误")
        qtbot.wait(50)

        assert accessed == [], f"取消后仍有槽函数访问工作表格: {accessed}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_query_slots_survive_deleted_table(window, test_data_dir, qtbot, monkeypatch):
    """表格 C++ 对象已析构时，查询槽函数仍须安全返回（CI 报错栈顶两帧）。"""
    tmp = _scan_and_query(window, qtbot, test_data_dir, "pilotstd_lifecycle_slot_")
    try:
        handler = window._core.query
        worker = handler._query_worker
        assert worker is not None
        if worker.isRunning():
            assert worker.wait(3000), "查询线程应在超时内结束"

        # 造一个已析构的表格：模拟"窗口先销毁、信号后到达"
        probe = QTableWidget()
        _sip.delete(probe)
        assert _sip.isdeleted(probe), "前置条件：探针控件必须已析构"
        monkeypatch.setattr(handler._deps.table, "get_work_table", lambda: probe)

        handler.on_query_batch_ready([(0, object())])
        handler.on_query_result_ready(0, object())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_find_row_by_seq_returns_minus_one_for_deleted_table(qapp):
    """表格已析构时 _find_row_by_seq 返回 -1（CI 栈帧 _table_ops.py:259）。"""
    from pilotstd.ui.main_window.parts._table_ops import _find_row_by_seq

    table = QTableWidget()
    table.setRowCount(1)
    table.setColumnCount(1)  # 必须先有列，否则 setItem 静默丢弃
    table.setItem(0, 0, QTableWidgetItem("1"))
    stub = SimpleNamespace(work_table=table)
    assert _find_row_by_seq(stub, 1) == 0, "正常表格应能找到序号 1"

    _sip.delete(table)
    assert _sip.isdeleted(table)
    assert _find_row_by_seq(stub, 1) == -1, "表格已析构时必须返回 -1 而不是抛异常"


def test_progress_pipeline_survives_deleted_objects(qapp):
    """进度管道或其定时器析构后，finish/reset/push 必须静默返回（CI 栈帧 unified_progress.py:60）。"""
    from pilotstd.ui.core.unified_progress import UnifiedProgressPipeline

    pipeline = UnifiedProgressPipeline()
    received: list[int] = []
    pipeline.progress_updated.connect(received.append)
    pipeline.push_pct(50)
    pipeline.finish()
    assert received and received[-1] == 100, "正常路径应发射 100"

    _sip.delete(pipeline._timer)  # 定时器先随窗口析构
    pipeline.finish()
    pipeline.reset()
    pipeline.push(1, 2)
    pipeline.push_pct(99)

    _sip.delete(pipeline)  # 管道整体析构
    pipeline.finish()
    pipeline.reset()
    pipeline.push_pct(10)


class _StuckWorker(QObject):
    """永不退出的假 worker：验证超时保活与计数（不真的起线程）。"""

    finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.stopped = False
        self.interrupted = False

    def stop(self) -> None:
        self.stopped = True

    def requestInterruption(self) -> None:
        self.interrupted = True

    def isRunning(self) -> bool:
        return True

    def wait(self, _ms: int) -> bool:
        return False  # 模拟"等不到退出"


def test_orphan_timeout_counts_and_releases(qapp, caplog):
    """超时未退出的线程必须计数 + 进保活列表，且自然结束后自动出列。"""
    from pilotstd.ui import qt_lifecycle as ql

    before = ql.orphan_timeout_total()
    worker = _StuckWorker()
    with caplog.at_level(logging.WARNING, logger="pilotstd.ui.qt_lifecycle"):
        assert ql.stop_worker_gracefully(worker, timeout_ms=1) is False

    assert worker.stopped and worker.interrupted, "必须先请求停止并请求中断，而不是强杀"
    assert ql.orphan_timeout_total() == before + 1, "超时次数必须累加（可观测）"
    assert ql.orphaned_worker_count() >= 1, "未退出的线程必须进保活列表"
    assert any("保活等待其自然结束" in r.getMessage() for r in caplog.records), "必须有告警留痕"

    worker.finished.emit()  # 线程自然结束
    assert ql.orphaned_worker_count() == 0, "线程结束后必须释放保活引用（不能只增不减）"


def test_orphan_timeout_escalates_to_error(qapp, caplog):
    """累计超时达到阈值后，告警升级为 error 并列出滞留线程（发现"永不退出"）。"""
    from pilotstd.ui import qt_lifecycle as ql

    workers = [_StuckWorker() for _ in range(ql._ORPHAN_WARN_THRESHOLD)]
    try:
        with caplog.at_level(logging.ERROR, logger="pilotstd.ui.qt_lifecycle"):
            for w in workers:
                ql.stop_worker_gracefully(w, timeout_ms=1)

        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert errors, "达到阈值后必须把 warning 升级为 error"
        message = errors[-1].getMessage()
        assert "疑似卡死线程" in message, f"error 文案应指明疑似卡死，实际: {message}"
        assert "_StuckWorker" in message, f"error 里要能看出是哪个线程，实际: {message}"
    finally:
        for w in workers:
            w.finished.emit()
    assert ql.orphaned_worker_count() == 0


# ══════════════════════════════════════════════════════════════════════════
# 技术债 #17a：worker 阻塞点设可中断上限
# ══════════════════════════════════════════════════════════════════════════
# 修复前：停止信号只让回调 `return`，底层 `*_stream` 继续跑完全部条目 →
# `stop_worker_gracefully(timeout_ms=5000)` 等满 5s → 计数 + 保活（只能人工重启容器）。
# 修复后：回调里的 `check_stop()` 抛 WorkerAborted 终止底层流，worker 快速退出。

_STREAM_ITEM_S = 0.01  # 单个"处理单元"耗时，模拟逐条解析/查询


class _SlowStreamMgr:
    """假管理器：`*_stream` 逐条回调，条目数足够多（不中途中断会跑很久）。"""

    def __init__(self, total: int = 20000, pause_event: Any = None) -> None:
        self.total = total
        self.ran = 0
        self.started = threading.Event()
        self._pause_event = pause_event

    def set_pause_event(self, ev: Any) -> None:
        self._pause_event = ev

    def _loop(self, on_progress: Any, on_result: Any = None) -> Any:
        """逐条"处理"并在每次处理后回调；`on_result` 存在时按 query 契约返回二元组。"""
        self.started.set()
        for i in range(self.total):
            time.sleep(_STREAM_ITEM_S)
            self.ran = i + 1
            if on_progress is not None:
                on_progress(i + 1, self.total)
            if on_result is not None:
                on_result(i, None)
        return ([], None) if on_result is not None else []

    def scan_stream(self, root_path: str, on_progress: Any = None, on_batch: Any = None) -> list[Any]:
        return self._loop(on_progress)

    def query_stream(self, parsed_list: Any, on_progress: Any = None, on_result: Any = None, **kw: Any) -> Any:
        return self._loop(on_progress, on_result)


def _stop_and_measure(worker: Any, timeout_ms: int = 5000) -> float:
    """调用统一停止入口并返回耗时（毫秒）。"""
    from pilotstd.ui.qt_lifecycle import stop_worker_gracefully

    t0 = time.monotonic()
    ok = stop_worker_gracefully(worker, timeout_ms=timeout_ms)
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert ok is True, f"worker 必须在超时前退出（实测 {elapsed_ms:.0f}ms / 预算 {timeout_ms}ms）"
    return elapsed_ms


@pytest.mark.parametrize("worker_kind", ["scan", "query"])
def test_worker_aborts_stream_within_budget(qapp, worker_kind):
    """#17a 量化验收：中断后 worker 必须在 timeout 的 80% 内退出，且不计入保活。"""
    from pilotstd.ui import qt_lifecycle as ql
    from pilotstd.ui.workers import QueryWorker, ScanWorker

    mgr = _SlowStreamMgr()
    worker = ScanWorker(mgr, "X:/") if worker_kind == "scan" else QueryWorker(mgr, [])
    orphan_before = ql.orphan_timeout_total()

    worker.start()
    assert mgr.started.wait(5.0), "假 stream 未启动"
    time.sleep(0.15)  # 让它真跑几条，确保是在"流进行中"被中断

    elapsed_ms = _stop_and_measure(worker, timeout_ms=5000)
    timeout_budget_ms = 5000 * 0.8

    assert worker.isFinished(), "停止后线程必须已结束"
    assert elapsed_ms < timeout_budget_ms, (
        f"退出耗时 {elapsed_ms:.0f}ms 超过预算 {timeout_budget_ms:.0f}ms（80% timeout）"
    )
    assert elapsed_ms < 500, f"实测量级应远小于 500ms，实测 {elapsed_ms:.0f}ms"
    assert ql.orphan_timeout_total() == orphan_before, "可中断的 worker 不得再走超时保活路径"
    assert mgr.ran < mgr.total, f"底层流必须被中止，而不是跑完（已处理 {mgr.ran}/{mgr.total}）"


class _ExceptionSwallowingMgr(_SlowStreamMgr):
    """模拟服务层"单条失败继续跑"的兜底写法（`manager/facade/_organize.py:106-123`）。

    该处把 `on_result` 包在 `try/except Exception` 内；若 `WorkerAborted` 继承 `Exception`，
    中断会被吞掉并继续跑完整条流 → 中断失效。故本类专门守卫"控制流异常不被兜底捕获"。
    """

    def scan_stream(self, root_path: str, on_progress: Any = None, on_batch: Any = None) -> list[Any]:
        self.started.set()
        for i in range(self.total):
            time.sleep(_STREAM_ITEM_S)
            self.ran = i + 1
            try:
                if on_progress is not None:
                    on_progress(i + 1, self.total)
            except Exception:  # noqa: S110 - 服务层通用兜底（被测行为）
                pass
        return []


def test_abort_survives_service_layer_except_exception(qapp):
    """#17a：WorkerAborted 必须继承 BaseException，否则被服务层 `except Exception` 吞掉。"""
    from pilotstd.ui.workers import ScanWorker

    mgr = _ExceptionSwallowingMgr()
    worker = ScanWorker(mgr, "X:/")

    worker.start()
    assert mgr.started.wait(5.0), "假 stream 未启动"
    time.sleep(0.15)

    elapsed_ms = _stop_and_measure(worker, timeout_ms=5000)
    assert worker.isFinished(), "停止后线程必须已结束"
    assert elapsed_ms < 500, f"被兜底捕获即会退化为 5s 超时，实测 {elapsed_ms:.0f}ms"
    assert mgr.ran < mgr.total, f"底层流必须被中止（已处理 {mgr.ran}/{mgr.total}）"


def test_paused_query_worker_is_interruptible(qapp):
    """#17a：暂停状态下收到停止请求也必须能退出（原实现是无超时 wait()，必然保活）。"""
    import threading as _threading

    from pilotstd.ui.workers import QueryWorker

    pause_event = _threading.Event()  # 永不 set → 模拟用户暂停
    mgr = _SlowStreamMgr(total=20000, pause_event=pause_event)
    worker = QueryWorker(mgr, [], pause_event=pause_event)

    worker.start()
    assert mgr.started.wait(5.0), "假 stream 未启动"
    time.sleep(0.3)  # 进入暂停等待（每 200ms 一次停止检查切片）

    elapsed_ms = _stop_and_measure(worker, timeout_ms=5000)
    assert worker.isFinished(), "暂停中的 worker 停止后必须已结束"
    assert elapsed_ms < 1500, f"暂停切片 200ms，退出应远快于 1.5s，实测 {elapsed_ms:.0f}ms"


def test_drive_enumerator_checks_interruption(qapp, monkeypatch):
    """#17a：DriveEnumerator 逐个盘符之间设检查点（网络盘 absolutePath 可能长时间阻塞）。"""
    from PyQt6.QtCore import QDir

    from pilotstd.ui.drive_enumerator import DriveEnumerator

    class _SlowDir:
        def __init__(self, i: int) -> None:
            self._i = i

        def absolutePath(self) -> str:
            time.sleep(0.02)
            return f"Z:/drive{self._i}"

    monkeypatch.setattr(QDir, "drives", staticmethod(lambda: [_SlowDir(i) for i in range(5000)]))

    worker = DriveEnumerator()
    worker.start()
    time.sleep(0.2)
    elapsed_ms = _stop_and_measure(worker, timeout_ms=5000)
    assert worker.isFinished(), "停止后枚举线程必须已结束"
    assert elapsed_ms < 500, f"逐盘检查点应快速退出，实测 {elapsed_ms:.0f}ms"

