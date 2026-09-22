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

import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

from PyQt6 import sip as _sip
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
