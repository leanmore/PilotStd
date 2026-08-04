# 标准文件管理工具
# 入口脚本：默认启动图形界面，命令行参数进入命令行模式

import argparse
import datetime
import faulthandler
import os
import sys
import threading
import traceback

from dotenv import load_dotenv

# 已废弃：防御性安全流包装类（详见历史）

# 打包模式：替换缺失的标准流（详见历史）

# 故障处理器仅开发时启用，打包交付后禁用（避免无控制台报错）
if not getattr(sys, "frozen", False):
    try:
        faulthandler.enable(file=sys.stderr, all_threads=True)
    except Exception:
        pass

# 加载环境配置文件（优先级：系统环境变量 > 配置文件）
load_dotenv(os.path.join(os.path.dirname(__file__) or ".", ".env"))

# ── 全局异常捕获：未捕获异常写入崩溃日志文件 ──
if getattr(sys, "frozen", False):
    _CRASH_LOG = os.path.join(os.path.dirname(sys.executable), "crash_log.txt")
else:
    _CRASH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt")


def _global_excepthook(exc_type, exc_value, exc_tb):
    """将所有未捕获的异常写入崩溃日志文件后调用默认处理器。"""
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
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _global_excepthook
threading.excepthook = _thread_excepthook  # type: ignore[assignment]


def main():
    from pilotstd.core.logger import LoggerManager

    logger = LoggerManager.get_logger("PilotStd")

    # ── 超级用户环境变量处理 ──
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
    args, remaining = parser.parse_known_args()

    if args.cli:
        # 将命令行参数传给子解析器，避免参数无法识别
        import sys as _sys

        _sys.argv = [_sys.argv[0], *remaining]
        from pilotstd.cli.commands import main as cli_main

        return cli_main()

    from pilotstd.ui.main_window import run

    try:
        run()
    except Exception:
        # 兜底：极端情况下全局异常钩子未能触发时仍写入崩溃日志（已禁用）
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
