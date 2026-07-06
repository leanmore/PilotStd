# PilotStd — 标准文件管理工具
# 入口脚本：默认启动 PyQt6 GUI，--cli 进入命令行模式

import argparse
import faulthandler
import io
import os
import sys

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
    faulthandler.enable(all_threads=True)
except (io.UnsupportedOperation, AttributeError, OSError):
    pass

# 加载 .env 文件（优先级：系统环境变量 > .env 文件）
load_dotenv(os.path.join(os.path.dirname(__file__) or ".", ".env"))


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

    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
