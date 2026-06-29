# pilotstd/cli/commands/expire.py — expire 子命令
import argparse

from pilotstd.cli.commands._shared import _make_manager


def cmd_expire(args: argparse.Namespace) -> int:
    """将过期标准文件移入 过期作废/ 目录。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))
    result = mgr.expire_files(args.files)
    print(f"已移动: {result['moved']}, 失败: {result['failed']}")
    for detail in result["details"]:
        print(f"  {detail}")
    return 0
