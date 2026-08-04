# 项目//命令/脚本—子命令
import argparse
import csv
import json
import sys

from pilotstd.cli.commands._shared import _make_manager


def cmd_normalize(args: argparse.Namespace) -> int:
    """解析文件名并输出规范化格式，不移动文件。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))
    results = mgr.normalize_files(args.files)

    if args.format == "json":
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["源文件", "代号", "顺序号", "年份", "规范化名称", "目标文件夹"])
        for r in results:
            writer.writerow(
                [
                    r["source"],
                    r["logical_code"],
                    r["number"],
                    r["year"],
                    r["normalized"],
                    r["folder"],
                ]
            )
    return 0
