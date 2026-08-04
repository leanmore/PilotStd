# 项目//命令/脚本—子命令
import argparse
import json

from pilotstd.cli.commands._shared import _make_manager


def cmd_auto(args: argparse.Namespace) -> int:
    """一键处理：扫描→查询→下载→规范化→归档，全自动。"""
    mgr = _make_manager(
        storage_root=getattr(args, "storage_root", None),
        use_cache=not getattr(args, "no_cache", False),
    )
    result = mgr.auto_run(args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == "json" else str(result))
    return 0
