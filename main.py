# PilotStd — 标准文件管理工具
# 入口脚本：默认启动 PyQt6 GUI，--cli 进入命令行模式

import argparse
import os
import sys

from dotenv import load_dotenv

# 加载 .env 文件（优先级：系统环境变量 > .env 文件）
# load_dotenv 默认不覆盖已存在的环境变量，保证系统环境变量优先
load_dotenv(os.path.join(os.path.dirname(__file__) or ".", ".env"))


def main():
    # ── SUPERUSER 环境变量处理 ──
    # 检测是否为 PyInstaller 打包环境
    is_packaged = getattr(sys, "frozen", False)

    if is_packaged:
        # ── Win / CLI 桌面端（打包后的 exe） ──
        # 优先使用系统环境变量，若无则使用默认值
        _su = os.getenv("SUPERUSER", "superadmin")
        if _su.lower() == "admin":
            # "admin" 用户名被禁止充当超级用户，回退到安全默认值
            print("WARNING: SUPERUSER cannot be 'admin', falling back to 'superadmin'", file=sys.stderr)
            _su = "superadmin"
        # 写入环境变量，供后续导入的模块读取
        os.environ["SUPERUSER"] = _su
    else:
        # ── Docker / 源码开发环境 ──
        # 必须设置 SUPERUSER 环境变量，否则拒绝启动
        _su = os.getenv("SUPERUSER")
        if not _su:
            print("FATAL: SUPERUSER environment variable is not set", file=sys.stderr)
            sys.exit(1)
        if _su.lower() == "admin":
            print("FATAL: SUPERUSER cannot be 'admin', please use a different username", file=sys.stderr)
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
