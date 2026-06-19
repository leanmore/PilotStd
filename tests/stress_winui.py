# tests/stress_winui.py
# WinUI 热启交叉对比测试 — 由 stress_driver.py 调用
#
# 用法（由驱动器调用）:
#   python -m pytest tests/stress_winui.py -v -s
#       --source D:\标准 --output E:\标准
#       --step1 <step1.json> --step2 <step2.json>
#
# 策略:
#   1. 加载 step1.json（CLI 冷启结果）作为期望值
#   2. 创建 MainWindow → run_auto(热启) → 等待全部 worker
#   3. 取 get_pipeline_stats() 实际值
#   4. 逐项交叉对比
#   5. 写 step2.json

import json
import logging
import os
import sys
import time

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import pytest
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger("stress_winui")


# ── QApplication fixture ─────────────────────────────────────


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setStyle("Fusion")
    # 初始化 LoggerManager——MainWindow(cfg, prj) 不走 run()，需手动初始化文件 handler
    from pilotstd.core.logger import LoggerManager

    LoggerManager(level=logging.INFO)
    yield app


# ── MainWindow fixture ───────────────────────────────────────


@pytest.fixture
def window(qapp, qtbot, request):
    """创建 MainWindow，使用与 CLI 相同 storage_root + 保留 DB（热启）。"""
    from pilotstd.core.config import ConfigManager
    from pilotstd.core.project import ProjectManager
    from pilotstd.ui.main_window import MainWindow

    source_dir = request.config.getoption("--source")
    output_dir = request.config.getoption("--output")

    cfg = ConfigManager()
    cfg.set("storage.root_dir", output_dir)
    cfg.set("query.use_cache", True)
    cfg.set("appearance.skip_welcome", True)
    cfg.set("announcement.auto_check", False)

    prj = ProjectManager()
    win = MainWindow(cfg, prj)
    win._suppress_dialogs = True
    win.show()
    qtbot.addWidget(win)
    qtbot.waitExposed(win)
    # 触发 StandardManager 同步初始化（QTimer 延迟可能尚未激发）
    _mgr = win._mgr
    assert win._mgr_ready, "StandardManager 初始化失败"
    # 设置路径为源目录
    win._menu_selected_path = source_dir

    yield win

    # 清理
    for h in list(logging.getLogger().handlers):
        if hasattr(win, "_log_handler") and h is win._log_handler:
            logging.getLogger().removeHandler(h)
    win.close()
    win.deleteLater()


# ── Worker 等待工具 ──────────────────────────────────────────


def _wait_worker(qtbot, window, attr, timeout=3600000):
    """等待 Worker 完成。默认 1 小时超时，远大于正常管线耗时。"""
    w = getattr(window, attr, None)
    if w is not None and w.isRunning():
        with qtbot.waitSignal(w.finished_signal, timeout=timeout):
            pass


# ── 测试: 热启 auto + 交叉对比 ────────────────────────────────


def test_winui_hot_cross_compare(window, qtbot, request):
    """WinUI 热启一键处理 → 取统计 → 与 CLI 冷启结果交叉对比。

    不再次清 DB，CLI 冷启写入的三表缓存直接复用。
    """
    source_dir = request.config.getoption("--source")
    step1_path = request.config.getoption("--step1")
    step2_path = request.config.getoption("--step2")
    if not source_dir or not step1_path or not step2_path:
        pytest.skip("需要 --source --step1 --step2（由 stress_driver.py 传入）")

    # 加载 CLI 冷启结果
    with open(step1_path, "r", encoding="utf-8") as f:
        step1 = json.load(f)
    expected = step1.get("summary", {})
    logger.info(
        "CLI 冷启期望值: scan=%d query_dl=%d query_ex=%d query_pe=%d dl_success=%d org_moved=%d",
        expected.get("scan_count", 0),
        expected.get("query_download", 0),
        expected.get("query_expire", 0),
        expected.get("query_pending", 0),
        expected.get("download_success", 0),
        expected.get("organize_moved", 0),
    )

    win = window
    t0 = time.time()

    # 触发 auto 管线
    logger.info("触发 WinUI run_auto...")
    win.run_auto(source_dir)

    # 等待统一 AutoWorker（替代原有 5 个独立 Worker）
    logger.info("等待 AutoWorker...")
    _wait_worker(qtbot, win, "_auto_worker")

    elapsed = time.time() - t0
    logger.info(f"WinUI auto 完成: {elapsed:.1f}s")

    # 取统计
    actual = win.get_pipeline_stats()
    logger.info(
        "WinUI 实际值: scan=%d query_dl=%d query_ex=%d query_pe=%d total=%d",
        actual["scan_count"],
        actual["query_download"],
        actual["query_expire"],
        actual["query_pending"],
        actual["query_total"],
    )

    # ── 交叉对比 ──
    comparisons = []
    all_pass = True

    _TOLERANCE = float(os.environ.get("PILOTSTD_TOLERANCE", "0.1"))

    def _cmp(label, exp_val, act_val, tolerance=_TOLERANCE):
        nonlocal all_pass
        ok = (
            abs(exp_val - act_val) / max(exp_val, 1) <= tolerance
            if exp_val > 0
            else act_val == 0
        )
        if not ok:
            all_pass = False
        comparisons.append(
            {
                "item": label,
                "cli_expected": exp_val,
                "winui_actual": act_val,
                "pass": ok,
                "tolerance": tolerance,
            }
        )
        logger.info(
            f"  交叉对比 {label}: CLI={exp_val} WinUI={act_val} → {'PASS' if ok else 'FAIL'}"
        )

    _cmp("scan_count", expected.get("scan_count", 0), actual["scan_count"])
    _cmp("query_download", expected.get("query_download", 0), actual["query_download"])
    _cmp("query_exact", expected.get("query_exact", 0), actual.get("query_exact", 0))

    # ── 三表读验证 ──
    from pilotstd.core.config import get_data_dir
    from pilotstd.core.db import Database

    db_path = os.path.join(get_data_dir(), "pilotstd.db")
    three_table = {}
    if os.path.exists(db_path):
        db = Database(db_path)
        for t in ["standard_info_cache", "file_index", "announcement_cache"]:
            try:
                n = db.fetchone(f"SELECT COUNT(*) as c FROM {t}")
                three_table[t] = n.get("c", 0) if n else 0
            except Exception:
                three_table[t] = 0
    logger.info("三表: %s", three_table)
    for t_name in ["standard_info_cache", "file_index", "announcement_cache"]:
        ok = three_table.get(t_name, 0) > 0
        comparisons.append(
            {
                "item": f"三表读_{t_name}",
                "count": three_table.get(t_name, 0),
                "pass": ok,
            }
        )
        if not ok:
            all_pass = False
        logger.info(
            f"  三表读 {t_name}: {three_table.get(t_name, 0)} → {'PASS' if ok else 'FAIL'}"
        )

    # ── 写 step2.json ──
    step2 = {
        "step": 2,
        "ts": time.strftime("%Y%m%d_%H%M%S"),
        "elapsed_s": round(elapsed, 1),
        "actual": actual,
        "expected": expected,
        "three_table": three_table,
        "comparisons": comparisons,
        "verdict": "PASS" if all_pass else "FAIL",
    }
    os.makedirs(os.path.dirname(step2_path), exist_ok=True)
    with open(step2_path, "w", encoding="utf-8") as f:
        json.dump(step2, f, ensure_ascii=False, indent=2)
    logger.info(f"step2.json 已写入: {step2_path}")

    assert all_pass, (
        f"交叉对比 FAIL: {len([c for c in comparisons if not c['pass']])} 项未通过"
    )
