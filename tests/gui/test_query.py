import os
import shutil
import sys
import tempfile

from tests.gui.helpers import wait_for_worker_and_ui
from tests.gui.helpers.predicates import worker_done

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def _copy_fixtures_to_tmp(test_data_dir):
    """把 fixtures 复制到临时目录，防止 _auto_move_expired 消耗原件。"""
    tmp = tempfile.mkdtemp(prefix="pilotstd_test_fixtures_")
    for name in os.listdir(test_data_dir):
        src = os.path.join(test_data_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, tmp)
    return tmp


def _effect_status_filled(window) -> bool:
    """表格「生效状态」列（col 4）是否至少有一行已写入。

    该列由 `on_query_result_ready` 在**每条结果到达时**写入（`build_result_cells` 的 col4 = result.status），
    所以它正是"查询结果已开始落地"的判据；用它替代固定 sleep。
    """
    table = window.work_table
    for row in range(table.rowCount()):
        item = table.item(row, 4)
        if item is not None and item.text():
            return True
    return False


def test_query_requires_scan_first(window, qtbot):
    """未导入时点击查询应弹出提示。"""
    window._parsed_results.clear()
    window._clear_table()
    window._on_query()
    qtbot.wait(200)
    assert len(window._parsed_results) == 0


def test_query_mock_populates_status(window, test_data_dir, qtbot):
    """mock 模式下扫描→查询后状态列应有值。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        wait_for_worker_and_ui(
            qtbot, window, "_scan_worker",
            ui_predicate=lambda: window.work_table.rowCount() > 0,
        )
        window._on_query()
        # 等查询线程真正结束（旧写法 qtbot.wait(1000) 是固定 sleep：worker 实测 0.6–1.7s，
        # 余量为负 → CI run 36253266299 已实证 flaky）
        wait_for_worker_and_ui(qtbot, window, "_query_worker", ui_predicate=worker_done)
        table = window.work_table
        assert table.rowCount() > 0
        for row in range(table.rowCount()):
            status_item = table.item(row, 1)
            if status_item:
                text = status_item.text()
                assert "查询" in text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_query_mock_changes_effect_status(window, test_data_dir, qtbot):
    """mock 查询后生效状态列应有值。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        wait_for_worker_and_ui(
            qtbot, window, "_scan_worker",
            ui_predicate=lambda: window.work_table.rowCount() > 0,
        )
        window._on_query()
        # 判据 = 「生效状态」列真的有值（col4 由结果到达时写入），不再赌固定 1000ms
        wait_for_worker_and_ui(
            qtbot, window, "_query_worker",
            ui_predicate=lambda: _effect_status_filled(window),
        )
        assert _effect_status_filled(window), "生效状态列（col 4）应有值：查询结果未写入表格"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_query_progress_bar_shows(window, test_data_dir, qtbot):
    """查询过程中进度条应可见。"""
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        qtbot.wait(300)
        window._on_query()
        qtbot.wait(200)
        assert window.progress_bar.isVisible()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_query_summary_after_query(window, test_data_dir, qtbot):
    """查询完成后 show_query_summary 不应被 _suppress_dialogs 阻断。
    回归测试：修复前 getattr(lambda, False) 始终为 True 导致弹窗永不显示。
    """
    tmp = _copy_fixtures_to_tmp(test_data_dir)
    try:
        window._run_scan(tmp)
        wait_for_worker_and_ui(
            qtbot, window, "_scan_worker",
            ui_predicate=lambda: window.work_table.rowCount() > 0,
        )
        window._on_query()
        wait_for_worker_and_ui(qtbot, window, "_query_worker", ui_predicate=worker_done)
        # 查询完成后直接调用 summary，验证不会因 lambda 对象误判而提前 return
        # 在 _suppress_dialogs=True 时弹窗本身不弹出，但方法应正常执行到构建阶段
        summary = window._core.query._summary
        buckets = summary.build_buckets()
        assert isinstance(buckets, dict)
        # 收紧（原断言带 `or True` 恒真）：查询结束后条目应已被 pipeline router 打上 next_action，
        # 并因此落进某个汇总桶
        assert any(p.next_action for p in window._parsed_results), "查询结束后应已给出 next_action"
        assert sum(len(v) for v in buckets.values()) >= 1, "查询结束后汇总分栏不应为空"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
