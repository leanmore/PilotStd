# pilotstd/cli/commands/organize.py — organize 子命令
import argparse
import json

from pilotstd.cli.commands._shared import _make_manager

logger = __import__("logging").getLogger("pilotstd.cli")


def cmd_organize(args: argparse.Namespace) -> int:
    """规范化文件名并归档到标准库。--source 指定源目录时先扫描再归档。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))
    source = getattr(args, "source", None)
    if source:
        parsed = mgr.scan_directory(source)
        logger.info("扫描完成: %d 条，开始归档...", len(parsed))
        result = mgr.archive_standards(parsed, word_source_root=source)
    else:
        result = mgr.archive_standards(mgr._parsed_results)
    print(json.dumps(result, ensure_ascii=False, indent=2) if getattr(args, "format", None) == "json" else str(result))
    return 0
