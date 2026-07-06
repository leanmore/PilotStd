# PilotStd — 标准文件管理工具
# 入口脚本：默认启动 PyQt6 GUI，--cli 进入命令行模式

import argparse
import datetime
import faulthandler
import io
import os
import sys
import threading
import traceback

from dotenv import load_dotenv


class _SafeStream(io.StringIO):
    """防御性文本流：替代 io.StringIO，提供 fileno/isatty 避免崩溃。

    PyInstaller --noconsole 模式下 sys.stderr/stdout 为 None，
    但 faulthandler、logging.StreamHandler、第三方库可能调用
    .fileno() 或 .isatty()。普通 StringIO 缺少这两个方法会抛
    io.UnsupportedOperation。
    """

    def fileno(self) -> int:
        # 返回 -1 可能被 os.write(-1, ...) 误用；抛出标准异常让调用方
        # 自行降级（logging.StreamHandler / faulthandler 会捕获后跳过）
        raise io.UnsupportedOperation("fileno")

    def isatty(self) -> bool:
        return False


# PyInstaller --noconsole 模式：替换缺失的标准流
if getattr(sys, "frozen", False):
    if sys.stderr is None:
        sys.stderr = _SafeStream()
    if sys.stdout is None:
        sys.stdout = _SafeStream()
    if sys.stdin is None:
        sys.stdin = _SafeStream()

# faulthandler 内部会调用 stderr.fileno()，_SafeStream 已兜底，但
# 极端环境（非 frozen 但 stderr 损坏）再加一层 try-except 保护
try:
    faulthandler.enable(file=sys.stderr, all_threads=True)
except (io.UnsupportedOperation, AttributeError, OSError):
    pass

# 加载 .env 文件（优先级：系统环境变量 > .env 文件）
load_dotenv(os.path.join(os.path.dirname(__file__) or ".", ".env"))

# ── 全局异常捕获：未捕获异常写入 crash_log.txt ──
_CRASH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt")


def _global_excepthook(exc_type, exc_value, exc_tb):
    """将所有未捕获的 Python 异常写入 crash_log.txt 后调用默认处理器。"""
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    msg = "".join(tb_lines)
    try:
        with open(_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"CRASH [{datetime.datetime.now().isoformat()}]\n")
            f.write(msg)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    """捕获后台线程中未处理的异常。"""
    exc_type = args.exc_type or type(args.exc_value) if args.exc_value else Exception
    exc_value = args.exc_value or Exception("unknown thread error")
    exc_tb = args.exc_traceback
    thread_name = args.thread.name if args.thread else "unknown"
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    msg = "".join(tb_lines)
    try:
        with open(_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"THREAD CRASH [{datetime.datetime.now().isoformat()}] thread={thread_name}\n")
            f.write(msg)
    except Exception:
        pass
    # 调用默认线程异常处理器
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _global_excepthook
threading.excepthook = _thread_excepthook  # type: ignore[assignment]


def main():
    from pilotstd.core.logger import LoggerManager

    logger = LoggerManager.get_logger("PilotStd")

    # ── SUPERUSER 环境变量处理 ──
    is_packaged = getattr(sys, "frozen", False)

    if is_packaged:
        _su = os.getenv("SUPERUSER", "superadmin")
        if _su.lower() == "admin":
            logger.warning("SUPERUSER cannot be 'admin', falling back to 'superadmin'")
            _su = "superadmin"
        os.environ["SUPERUSER"] = _su
    else:
        _su = os.getenv("SUPERUSER")
        if not _su:
            logger.critical("FATAL: SUPERUSER environment variable is not set")
            sys.exit(1)
        if _su.lower() == "admin":
            logger.critical("FATAL: SUPERUSER cannot be 'admin', please use a different username")
            sys.exit(1)

    parser = argparse.ArgumentParser(prog="pilotstd", description="PilotStd 标准文件管理工具")
    parser.add_argument("--cli", action="store_true", help="命令行模式")
    args, _ = parser.parse_known_args()

    if args.cli:
        from pilotstd.cli.commands import main as cli_main

        return cli_main()

    from pilotstd.ui.main_window import run

    try:
        run()
    except Exception:
        # 兜底：极端情况下 sys.excepthook 未能触发时仍写入 crash_log
        tb_lines = traceback.format_exception(*sys.exc_info())
        msg = "".join(tb_lines)
        try:
            with open(_CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"FATAL [{datetime.datetime.now().isoformat()}]\n")
                f.write(msg)
        except Exception:
            pass
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
