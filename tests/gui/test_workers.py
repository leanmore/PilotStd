import threading
from unittest.mock import MagicMock

from pilotstd.query.models import QueryResult
from pilotstd.ui.workers import QueryWorker


def _make_mock_manager(results_count: int):
    """创建一个模拟 StandardManager，其 query() 返回指定数量的假结果。"""
    mgr = MagicMock()
    results = []
    for i in range(results_count):
        r = QueryResult(
            standard_number=f"GB/T {i}",
            standard_name=f"测试标准_{i}",
            status="现行",
            source_site="mock",
        )
        results.append(r)
    mgr.query.return_value = (results, {})
    return mgr


def test_query_worker_emits_batch_ready(qtbot):
    """QueryWorker batch_ready 信号覆盖全部查询项。"""
    mgr = _make_mock_manager(3)
    parsed_list = [
        ("GB/T", 1, 2020, "", None),
        ("GB/T", 2, 2020, "", None),
        ("SH/T", 3010, 2018, "", None),
    ]
    worker = QueryWorker(mgr, parsed_list)
    batches = []
    worker.batch_ready.connect(lambda b: batches.extend(b))
    with qtbot.waitSignal(worker.finished_signal, timeout=5000):
        worker.start()
    assert len(batches) == 3, f"batch_ready 应覆盖全部 3 条，实际 {len(batches)}"


def test_query_worker_stops_on_stop(qtbot):
    """stop() 后 QueryWorker 不发射 batch_ready，提前结束。"""
    import time

    mgr = MagicMock()
    query_started = threading.Event()

    def delayed_query(parsed_list, progress_callback=None):
        # 通知主线程查询已开始，然后短暂等待让 stop() 有机会执行
        query_started.set()
        time.sleep(0.2)
        results = []
        for i in range(100):
            r = QueryResult(
                standard_number=f"GB/T {i}",
                standard_name=f"测试标准_{i}",
                status="现行",
                source_site="mock",
            )
            results.append(r)
        return results, {}

    mgr.query.side_effect = delayed_query
    parsed_list = [("GB/T", i, 2020, "", None) for i in range(100)]
    worker = QueryWorker(mgr, parsed_list)
    processed = []
    worker.batch_ready.connect(lambda b: processed.extend(b))
    worker.start()
    # 等待查询线程进入 query() 后再调用 stop()，确保 _stopped 在 query 返回前被设置
    query_started.wait(timeout=5)
    worker.stop()
    worker.wait(5000)
    assert len(processed) == 0, (
        f"stop() 后不应发射 batch_ready，实际 {len(processed)} 条"
    )
