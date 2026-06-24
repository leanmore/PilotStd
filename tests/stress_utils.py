# tests/stress_utils.py
# 压力测试公共工具模块 —— 统一日志、进度、子进程、判定
#
# 日志统一写入 logs/app.log（通过 LoggerManager），不再创建独立 stress_*.log 文件。

import logging
import os
import subprocess
import sys
import time
from typing import Optional

# ── 统一日志配置 ─────────────────────────────────────────────────
# 委托 LoggerManager 管理，全局只初始化一次

_log_initialized = False


def setup_stress_logging(name: str) -> logging.Logger:
    """为压力测试脚本获取统一 logger，日志写入 logs/app.log。

    首次调用时初始化 LoggerManager（若尚未初始化），
    后续调用直接返回对应 name 的 logger。
    """
    global _log_initialized
    if not _log_initialized:
        _proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _proj_root not in sys.path:
            sys.path.insert(0, _proj_root)
        from pilotstd.core.logger import LoggerManager

        LoggerManager.get_logger("stress")  # 触发 LoggerManager 初始化
        _log_initialized = True
    return logging.getLogger(name)


# ── 统一判定工具 ──────────────────────────────────────────────────

_checks: list[tuple[str, bool, str]] = []


def check(label: str, ok, detail: str = ""):
    """记录一项检查结果（PASS/FAIL/SKIP）。"""
    _checks.append((label, ok, detail))
    logger = logging.getLogger("stress")
    icon = "PASS" if ok else "FAIL" if ok is False else "SKIP"
    logger.info("  %s %s%s", icon, label, f" — {detail}" if detail else "")
    logger.info(
        "[TRACE-C] check: name=%r ok=%r ok_type=%s detail=%r",
        label,
        ok,
        type(ok).__name__,
        detail,
    )


def verdict() -> bool:
    """输出判定汇总并返回是否全部通过。"""
    logger = logging.getLogger("stress")
    total = len(_checks)
    passed = sum(1 for _, ok, _ in _checks if ok)
    failed = sum(1 for _, ok, _ in _checks if ok is False)
    skipped = total - passed - failed
    logger.info(
        "[TRACE-C] verdict: total=%d passed=%d failed=%d skipped=%d",
        total,
        passed,
        failed,
        skipped,
    )
    for label, ok, detail in _checks:
        status = "PASS" if ok else "FAIL" if ok is False else "SKIP"
        logger.info("[TRACE-C] verdict_step: name=%r status=%s detail=%r", label, status, detail)
    logger.info("=" * 60)
    logger.info("判定: %s (%d/%d)", "PASS" if passed == total else "FAIL", passed, total)
    for label, ok, detail in _checks:
        if not ok:
            logger.info("  FAIL %s — %s", label, detail)
    logger.info("=" * 60)
    return passed == total


def get_check_results() -> list:
    """返回所有已记录的检查结果列表，供外部汇总报告使用。"""
    return list(_checks)


# ── 统一子进程执行 ───────────────────────────────────────────────


def run_visible(cmd: list, timeout: int = 3600, step: str = "", cwd: str | None = None) -> int:
    """以可见控制台窗口运行子进程。返回 exit code。"""
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

    优先级：ConfigManager(filepath=config_path) > 环境变量 > 报错退出。
    """
    base_url = os.environ.get("PILOTSTD_BASE_URL", "")
    username = os.environ.get("PILOTSTD_USERNAME", "")
    password = os.environ.get("PILOTSTD_PASSWORD", "")

    if config_path and os.path.exists(config_path):
        from pilotstd.core.config import ConfigManager

        cm = ConfigManager(filepath=config_path)
        base_url = cm.get("docker.url") or base_url
        username = cm.get("docker.username") or username
        password = cm.get("docker.password") or password

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


# ── 版本一致性校验 ──────────────────────────────────────────────────


def normalize_version(v: str) -> str:
    """剥离前导 v 和 -dirty/-dev 后缀，返回纯数字版本号。"""
    v = v.strip().lstrip("v")
    for sep in ("-dirty", "-dev", "-"):
        if sep in v:
            v = v.split(sep)[0]
    return v


def check_version_consistency(expected: str = "") -> bool:
    """比对运行环境中的 __version__ 与预期版本。"""
    logger = logging.getLogger("stress")
    if not expected:
        expected = os.environ.get("EXPECTED_VERSION", "")
    if not expected:
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--dirty"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                expected = result.stdout.strip()
        except Exception:
            pass
    if not expected:
        logger.warning("无法确定预期版本，跳过版本校验")
        return True

    try:
        from pilotstd import __version__ as actual
    except ImportError:
        logger.error("无法导入 pilotstd.__version__，版本校验失败")
        return False

    exp_norm = normalize_version(expected)
    act_norm = normalize_version(actual)
    if exp_norm != act_norm:
        logger.error(
            "[FATAL] 版本不一致: 预期=%s (归一化=%s), 实际=%s (归一化=%s)",
            expected,
            exp_norm,
            actual,
            act_norm,
        )
        return False
    logger.info("版本一致: 预期=%s 实际=%s", expected, actual)
    return True


# ── 日志双写 ──────────────────────────────────────────────────────


def log_to_file_and_console(msg: str, log_file: str, level: str = "INFO"):
    """同时写入日志文件和控制台。"""
    print(msg)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{level}] {msg}\n")
