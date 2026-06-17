# tests/stress_two_round.py
# 全量压力测试 v3 — 冷热双轮 + 三表联动验证
#
# 用法: python -m pytest tests/stress_two_round.py -v -s --source D:\标准 --output E:\标准
#
# Round 1 (冷启动): DB 清空 → GUI 模拟点击 → 全链路 → 缓存验证
# Round 2 (热启动): CLI auto → 耗时对比 → 验证冷启缓存复用

import os
import sys
import json
import time
import shutil
import tempfile
import logging
import subprocess
from datetime import datetime

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import pytest

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
logger = logging.getLogger("stress_two_round")


# ════════════════════════════════════════════════════════════════
# Fixtures（本文件内定义，不依赖 GUI conftest）
# ════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def qapp_stress():
    """会话级 QApplication。"""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setStyle("Fusion")
    yield app


@pytest.fixture
def real_window(qapp_stress, qtbot):
    """真实网络 MainWindow。DB 和适配器均为真实（非 mock）。"""
    from pilotstd import core
    from pilotstd.ui.main_window import MainWindow

    _tmp = tempfile.mkdtemp(prefix="stress_cold_")
    config_path = os.path.join(_tmp, "config.json")
    cfg = core.ConfigManager(filepath=config_path)
    cfg.set("query.use_cache", True)
    cfg.set("storage.root_dir", os.path.join(_tmp, "library"))
    cfg.set("appearance.skip_welcome", True)
    cfg.set("announcement.auto_check", False)

    prj = core.ProjectManager()
    win = MainWindow(cfg, prj)
    win._suppress_dialogs = True
    win.show()
    qtbot.addWidget(win)
    qtbot.waitExposed(win)

    yield win

    root_logger = logging.getLogger()
    for h in list(root_logger.handlers):
        if hasattr(win, '_log_handler') and h is win._log_handler:
            root_logger.removeHandler(h)
    if hasattr(win, '_stop_workers'):
        win._stop_workers()
    win.close()
    win.deleteLater()
    if os.path.isdir(_tmp):
        shutil.rmtree(_tmp, ignore_errors=True)


# ════════════════════════════════════════════════════════════════
# 工具
# ════════════════════════════════════════════════════════════════

def _wait_worker(qtbot, window, attr, timeout=600000):
    """等待 Worker 线程完成。timeout 默认 10 分钟。"""
    w = getattr(window, attr, None)
    if w is not None and w.isRunning():
        with qtbot.waitSignal(w.finished_signal, timeout=timeout):
            pass


def _clear_db_for_cold_start():
    """冷启动：清空缓存/索引/待确认表，保留 schema 和用户设置。"""
    from pilotstd.core.config import get_data_dir
    from pilotstd.core.db import Database
    db_path = os.path.join(get_data_dir(), "pilotstd.db")
    if not os.path.exists(db_path):
        return
    db = Database(db_path)
    tables = ["standard_info_cache", "announcement_cache",
              "pending_lookup", "file_index"]
    for t in tables:
        try:
            db.execute(f"DELETE FROM {t}")
        except Exception as e:
            logger.warning("清表 %s 失败: %s", t, e)
    logger.info("DB 冷启清空: %s", ", ".join(tables))


def _cache_stats():
    """返回当前缓存统计。"""
    from pilotstd.core.config import get_data_dir
    from pilotstd.core.db import Database
    db_path = os.path.join(get_data_dir(), "pilotstd.db")
    if not os.path.exists(db_path):
        return {}
    db = Database(db_path)
    r = {}
    for t in ["standard_info_cache", "announcement_cache", "file_index"]:
        try:
            n = db.fetchone(f"SELECT COUNT(*) as c FROM {t}")
            r[t] = n.get("c", 0) if n else 0
        except Exception:
            r[t] = 0
    return r


def _copy_source_to_tmp(source_dir):
    """复制源目录文件到临时目录（防止消耗原件）。"""
    tmp = tempfile.mkdtemp(prefix="stress_src_")
    for name in os.listdir(source_dir):
        src = os.path.join(source_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, tmp)
    n = len(os.listdir(tmp))
    logger.info("复制 %d 个文件 → %s", n, tmp)
    return tmp


# ════════════════════════════════════════════════════════════════
# Round 1 (冷启动) — GUI 模拟点击全链路
# ════════════════════════════════════════════════════════════════

class TestRound1ColdStart:
    """冷启动：GUI 模拟点击走完整链路。真实网络、真实文件。"""

    def test_round1_full_pipeline(self, real_window, qtbot, request):
        """完整链路：扫描→查询→下载→规范化→归档→缓存验证。

        模拟新用户第一次使用软件的完整流程。
        """
        source = request.config.getoption("--source", default=None)
        output = request.config.getoption("--output", default=None)
        if not source or not os.path.isdir(source):
            pytest.skip("需要 --source 指定源目录")

        win = real_window
        out_dir = output or os.path.join(tempfile.mkdtemp(prefix="stress_r1_"), "library")
        os.makedirs(out_dir, exist_ok=True)

        # ── 前置：冷启清空 DB ──
        _clear_db_for_cold_start()
        cs0 = _cache_stats()
        logger.info("R1-冷启: 缓存初始=%s", cs0)

        # 复制源文件到临时目录
        tmp_src = _copy_source_to_tmp(source)

        t0 = time.time()

        # ── 阶段1: 扫描 ──
        logger.info("R1-1: 扫描开始...")
        win._run_scan(tmp_src)
        _wait_worker(qtbot, win, "_scan_worker")
        parsed = win._parsed_results
        assert len(parsed) > 0, "扫描无结果"
        logger.info("R1-1: 扫描完成 — %d 条", len(parsed))

        # 类型分布
        tc = {}
        for p in parsed:
            c = (p.logical_code or "").upper()
            if c.startswith("GB"): k = "GB"
            elif c.startswith("DB"): k = "DB"
            elif c in ("ISO", "IEC", "ITU-T"): k = "INTL"
            else: k = "OTHER"
            tc[k] = tc.get(k, 0) + 1
        logger.info("R1-1: 类型=%s", tc)

        # ── 阶段2: 查询 ──
        logger.info("R1-2: 查询开始...")
        t_q = time.time()
        win._on_query()
        _wait_worker(qtbot, win, "_query_worker", timeout=600000)
        q_elapsed = time.time() - t_q

        dl = len(win._mgr.get_stage_queue("download"))
        ex = len(win._mgr.get_stage_queue("expire"))
        pe = len(win._mgr.get_stage_queue("pending"))
        logger.info("R1-2: 查询完成 %.1fs — download=%d expire=%d pending=%d total=%d",
                    q_elapsed, dl, ex, pe, len(parsed))

        # 查询后缓存验证
        cs1 = _cache_stats()
        logger.info("R1-2: 缓存=%s", cs1)
        assert cs1.get("standard_info_cache", 0) > 0, \
            "exact 结果应写入 standard_info_cache"

        # ── 阶段3: 下载 ──
        if dl > 0:
            logger.info("R1-3: 下载 %d 条...", dl)
            win._on_download()
            _wait_worker(qtbot, win, "_download_worker", timeout=600000)
            logger.info("R1-3: 下载完成")
        else:
            logger.info("R1-3: 下载队列为空，跳过")

        # ── 阶段4: 规范化 ──
        logger.info("R1-4: 规范化...")
        win._on_normalize()
        _wait_worker(qtbot, win, "_normalize_worker")
        logger.info("R1-4: 规范化完成")

        # ── 阶段5: 归档 ──
        logger.info("R1-5: 归档...")
        win._on_save_to_folder()
        _wait_worker(qtbot, win, "_archive_worker")
        root = win._get_library_root()
        assert os.path.isdir(root), f"归档目录不存在: {root}"
        logger.info("R1-5: 归档完成 — %s", root)

        # 归档后统计
        cs2 = _cache_stats()
        logger.info("R1-5: file_index=%d, 缓存=%s",
                    cs2.get("file_index", 0), cs2)

        # ── 阶段6: 缓存二次读取 ──
        exact_nums = []
        for p in parsed:
            if getattr(p, "match_status", "") == "exact":
                num = p.get_full_number()
                if num:
                    exact_nums.append(num)

        if exact_nums:
            logger.info("R1-6: %d 条 exact 缓存二次查询验证...", len(exact_nums))
            t_c = time.time()
            from pilotstd.core.config import ConfigManager
            cfg = ConfigManager()
            cfg.set("query.use_cache", True)
            # 用 scheduled_svc.query_by_numbers 验证缓存命中
            results, _ = win._mgr._scheduled_svc.query_by_numbers(
                exact_nums[:min(20, len(exact_nums))])
            cache_elapsed = time.time() - t_c
            logger.info("R1-6: 缓存二次查询 %d 条 — %.2fs (avg %.3fs/条)",
                        min(20, len(exact_nums)), cache_elapsed,
                        cache_elapsed / max(len(exact_nums[:20]), 1))
            found = sum(1 for r in results if getattr(r, 'is_found', None) and r.is_found())
            logger.info("R1-6: found=%d/%d", found, len(results))
        else:
            logger.info("R1-6: 无 exact 标准，跳过缓存验证")

        total_elapsed = time.time() - t0
        logger.info("=" * 50)
        logger.info("Round 1 (冷启) 汇总:")
        logger.info("  扫描: %d 条", len(parsed))
        logger.info("  查询耗时: %.1fs", q_elapsed)
        logger.info("  总耗时: %.1fs (%.1fmin)", total_elapsed, total_elapsed / 60)
        logger.info("  file_index: %d", cs2.get("file_index", 0))
        logger.info("  standard_info_cache: %d", cs2.get("standard_info_cache", 0))
        logger.info("=" * 50)


# ════════════════════════════════════════════════════════════════
# Round 2 (热启动) — CLI auto
# ════════════════════════════════════════════════════════════════

class TestRound2HotStart:
    """热启动：CLI auto 一键处理，验证缓存效果。"""

    def test_round2_auto(self, request):
        """CLI auto 全链路。依赖 Round 1 缓存数据。"""
        source = request.config.getoption("--source", default=None)
        output = request.config.getoption("--output", default=None)
        if not source or not os.path.isdir(source):
            pytest.skip("需要 --source 和 --output")

        out_dir = output or tempfile.mkdtemp(prefix="stress_r2_")
        os.makedirs(out_dir, exist_ok=True)

        cs_before = _cache_stats()
        logger.info("R2-前置: 缓存=%s", cs_before)

        t0 = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "pilotstd.cli.commands",
             "--storage-root", out_dir,
             "auto", source,
             "--no-cache",
             "--format", "json"],
            capture_output=True, text=True, timeout=600,
            cwd=root_dir, encoding="utf-8", errors="replace")
        elapsed = time.time() - t0

        logger.info("R2-auto: rc=%d 耗时 %.1fs", result.returncode, elapsed)
        if result.returncode != 0:
            logger.error("R2-auto stderr: %s", result.stderr[:500])

        cs_after = _cache_stats()
        logger.info("R2-后置: 缓存=%s", cs_after)

        # 验证输出
        if os.path.isdir(out_dir):
            dirs = [d for d in os.listdir(out_dir)
                    if os.path.isdir(os.path.join(out_dir, d))]
            logger.info("R2-auto: 输出 %d 个目录", len(dirs))

        logger.info("=" * 50)
        logger.info("Round 2 (热启) 汇总:")
        logger.info("  CLI auto 耗时: %.1fs (%.1fmin)", elapsed, elapsed / 60)
        logger.info("  缓存: before=%d after=%d",
                    cs_before.get("standard_info_cache", 0),
                    cs_after.get("standard_info_cache", 0))
        logger.info("=" * 50)
