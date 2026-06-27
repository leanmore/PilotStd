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
