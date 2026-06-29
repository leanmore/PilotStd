# pilotstd/cli/commands/pending.py — pending 子命令
import argparse
import csv
import json
import sys

from pilotstd.cli.commands._shared import _make_manager


def cmd_pending(args: argparse.Namespace) -> int:
    """查看/导出待确认清单。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))
    items = mgr.get_pending_items()

    if args.format == "json":
        json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
    elif args.output:
        with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["标准编号", "文件名", "网站名称", "状态", "匹配状态", "来源站点"])
            for item in items:
                w.writerow(
                    [
                        item.get(k, "")
                        for k in (
                            "standard_number",
                            "std_name",
                            "found_name",
                            "effect_status",
                            "match_status",
                            "source_site",
                        )
                    ]
                )
        print(f"已导出 {len(items)} 条 → {args.output}")
    else:
        for item in items:
            print(f"  {item.get('standard_number', '')} | {item.get('std_name', '')}")
        print(f"\n共 {len(items)} 条待确认")
    return 0
