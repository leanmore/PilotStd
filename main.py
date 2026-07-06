# PilotStd — 标准文件管理工具
# 入口脚本：默认启动 PyQt6 GUI，--cli 进入命令行模式

import argparse
import faulthandler
import io
import os
import sys

from dotenv import load_dotenv

# PyInstaller --noconsole 模式下 sys.stderr 为 None
# 不仅 print(..., file=sys.stderr) 会崩溃，LoggerManager 的 StreamHandler 也会
# 必须在任何 logging 初始化之前完成替换
if getattr(sys, "frozen", False) and sys.stderr is None:
    sys.stderr = io.StringIO()
    sys.stdout = io.StringIO()

faulthandler.enable()

# 加载 .env 文件（优先级：系统环境变量 > .env 文件）
load_dotenv(os.path.join(os.path.dirname(__file__) or ".", ".env"))


def main():
    # 惰性初始化：LoggerManager 首次 get_logger 时自动创建（Console + File handler）
    # 必须在 io.StringIO 修复之后、首次 logger 调用之前执行
    from pilotstd.core.logger import LoggerManager

    logger = LoggerManager.get_logger("PilotStd")

    # ── SUPERUSER 环境变量处理 ──
    is_packaged = getattr(sys, "frozen", False)

    if is_packaged:
        # ── Win / CLI 桌面端（打包后的 exe） ──
        _su = os.getenv("SUPERUSER", "superadmin")
        if _su.lower() == "admin":
            logger.warning("SUPERUSER cannot be 'admin', falling back to 'superadmin'")
            _su = "superadmin"
        os.environ["SUPERUSER"] = _su
    else:
        # ── Docker / 源码开发环境 ──
        _su = os.getenv("SUPERUSER")
        if not _su:
            logger.critical("FATAL: SUPERUSER environment variable is not set")
            sys.exit(1)
        if _su.lower() == "admin":
            logger.critical("FATAL: SUPERUSER cannot be 'admin', please use a different username")
            sys.exit(1)

    # ── 后续原有代码不变 ──
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
