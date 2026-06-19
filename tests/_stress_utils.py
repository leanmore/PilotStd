# tests/_stress_utils.py
# 压力测试公共工具模块 —— 统一日志、进度、子进程、判定
#
# 替代各 stress_*.py 文件中重复的 StreamHandler/FileHandler/_check/_verdict 等
# 重复代码。所有 stress_*.py 从此模块导入公共函数。

import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional

# ── 统一日志配置 ─────────────────────────────────────────────────
# 调用一次，所有 stress_*.py 共用，不再各自造 StreamHandler/FileHandler

_log_initialized = False


def setup_stress_logging(name: str) -> logging.Logger:
    """为压力测试脚本设置统一日志：控制台 + 文件双通道。
    全局只初始化一次，后续调用只返回对应 name 的 logger。"""
    global _log_initialized
    if not _log_initialized:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(
            log_dir, f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(
            logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")
        )
        root.addHandler(ch)

        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S"
            )
        )
        root.addHandler(fh)

        for noisy in ("urllib3", "requests", "lxml", "httpx", "PIL"):
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
    logger.info(
        "判定: %s (%d/%d)", "PASS" if passed == total else "FAIL", passed, total
    )
    for label, ok, detail in _checks:
        if not ok:
            logger.info("  FAIL %s — %s", label, detail)
    logger.info("=" * 60)
    return passed == total


# ── 统一子进程执行（可见控制台窗口）───────────────────────────────


def run_visible(cmd: list, timeout: int = 3600, step: str = "", cwd: str = None) -> int:
    """以可见控制台窗口运行子进程。返回 exit code。"""
    import subprocess

    logger = logging.getLogger("stress")
    logger.info(">>> 启动: %s", " ".join(cmd))
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            cwd=cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
        elapsed = time.time() - t0
        logger.info("<<< 完成: rc=%d 耗时 %.0fs", result.returncode, elapsed)
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.info("<<< 超时: %s (%ds)", step, timeout)
        return -1


# ── 统一 Docker 凭证加载 ───────────────────────────────────────────


def load_docker_credentials(config_path: Optional[str] = None) -> dict:
    """统一的 Docker 凭证加载，所有压测脚本共用。

    优先级：命令行 --config JSON > 环境变量 > 报错退出。
    不允许空值或默认值继续执行，防止静默跳过 Docker 测试。

    Args:
        config_path: --config 指向的 JSON 配置文件路径（可选）

    Returns:
        {"base_url": str, "username": str, "password": str}

    Raises:
        SystemExit: 缺少任一凭证时退出，打印帮助信息
    """
    import json as _json

    base_url = os.environ.get("PILOTSTD_BASE_URL", "")
    username = os.environ.get("PILOTSTD_USERNAME", "")
    password = os.environ.get("PILOTSTD_PASSWORD", "")

    # --config JSON 文件覆盖环境变量
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = _json.load(f)
        docker_cfg = cfg.get("docker", {})
        if docker_cfg:
            base_url = docker_cfg.get("url", base_url)
            username = docker_cfg.get("username", username)
            password = docker_cfg.get("password", password)

    missing = []
    if not base_url:
        missing.append("PILOTSTD_BASE_URL 或 docker.url")
    if not username:
        missing.append("PILOTSTD_USERNAME 或 docker.username")
    if not password:
        missing.append("PILOTSTD_PASSWORD 或 docker.password")

    if missing:
        print(
            "错误: 缺少 Docker 凭证，请通过以下方式之一提供:\n"
            "  1. 环境变量:\n"
            "     set PILOTSTD_BASE_URL=http://<host>:<port>\n"
            "     set PILOTSTD_USERNAME=<用户名>\n"
            "     set PILOTSTD_PASSWORD=<密码>\n"
            "  2. --config JSON 文件:\n"
            '     {"docker": {"url": "http://<host>:<port>", '
            '"username": "<用户名>", "password": "<密码>"}}',
            file=sys.stderr,
        )
        sys.exit(1)

    return {"base_url": base_url, "username": username, "password": password}
