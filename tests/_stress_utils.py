# tests/_stress_utils.py
# 压力测试公共工具模块 —— 统一日志、进度、子进程、判定
#
# 替代各 stress_*.py 文件中重复的 StreamHandler/FileHandler/_check/_verdict 等
# 重复代码。所有 stress_*.py 从此模块导入公共函数。

import os
import sys
import time
import logging
from datetime import datetime


# ── 统一日志配置 ─────────────────────────────────────────────────
# 调用一次，所有 stress_*.py 共用，不再各自造 StreamHandler/FileHandler

_log_initialized = False

def setup_stress_logging(name: str) -> logging.Logger:
    """为压力测试脚本设置统一日志：控制台 + 文件双通道。
    全局只初始化一次，后续调用只返回对应 name 的 logger。"""
    global _log_initialized
    if not _log_initialized:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(
            log_dir, f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s %(message)s", datefmt="%H:%M:%S"))
        root.addHandler(ch)

        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S"))
        root.addHandler(fh)

        for noisy in ('urllib3', 'requests', 'lxml', 'httpx', 'PIL'):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        _log_initialized = True
    return logging.getLogger(name)


# ── 统一判定工具 ──────────────────────────────────────────────────

_checks = []

def check(label: str, ok, detail: str = ""):
    """记录一项检查结果（PASS/FAIL/SKIP）。"""
    _checks.append((label, ok, detail))
    logger = logging.getLogger("stress")
    icon = "PASS" if ok else "FAIL" if ok is False else "SKIP"
    logger.info("  %s %s%s", icon, label, f" — {detail}" if detail else "")

def verdict() -> bool:
    """输出判定汇总并返回是否全部通过。"""
    logger = logging.getLogger("stress")
    total = len(_checks)
    passed = sum(1 for _, ok, _ in _checks if ok)
    logger.info("=" * 60)
    logger.info("判定: %s (%d/%d)", "PASS" if passed == total else "FAIL", passed, total)
    for label, ok, detail in _checks:
        if not ok:
            logger.info("  FAIL %s — %s", label, detail)
    logger.info("=" * 60)
    return passed == total


# ── 统一子进程执行（可见控制台窗口）───────────────────────────────

def run_visible(cmd: list, timeout: int = 3600, step: str = "",
                cwd: str = None) -> int:
    """以可见控制台窗口运行子进程。返回 exit code。"""
    import subprocess
    logger = logging.getLogger("stress")
    logger.info(">>> 启动: %s", ' '.join(cmd))
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, timeout=timeout,
            cwd=cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        elapsed = time.time() - t0
        logger.info("<<< 完成: rc=%d 耗时 %.0fs", result.returncode, elapsed)
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.info("<<< 超时: %s (%ds)", step, timeout)
        return -1
