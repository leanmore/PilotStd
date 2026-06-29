# pilotstd/cli/commands/scan.py — scan 子命令
import argparse
import csv
import json
import sys

from pilotstd.cli.commands._shared import _make_manager


def cmd_scan(args: argparse.Namespace) -> int:
    """扫描目录（支持多目录），输出解析结果。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))

    parsed = []
    for path in args.paths:
        parsed.extend(mgr.scan_directory(path))

    if args.format == "json":
        data = [
            {
                "index": i + 1,
                "code": p.logical_code,
                "number": p.number,
                "year": p.year,
                "part": p.part,
                "name": p.std_name,
                "full_number": p.get_full_number(),
            }
            for i, p in enumerate(parsed)
        ]
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["序号", "代号", "顺序号", "年份", "部分号", "标准名称", "完整编号"])
        for i, p in enumerate(parsed):
            writer.writerow(
                [
                    i + 1,
                    p.logical_code,
                    p.number,
                    p.year,
                    p.part or "",
                    p.std_name,
                    p.get_full_number(),
                ]
            )
    return 0
