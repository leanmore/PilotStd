# pilotstd/cli/commands/task.py — task 子命令
import argparse
import csv
import json
import sys

from pilotstd.cli.commands._shared import _make_manager


def cmd_task(args: argparse.Namespace) -> int:
    """查看任务队列状态。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))
    tasks = mgr.task_queue.list_all(limit=args.limit)
    if not tasks:
        print("暂无任务记录。")
        return 0

    if args.format == "json":
        data = [
            {
                "task_id": t.task_id,
                "type": t.task_type.value,
                "status": t.status.value,
                "total": t.total_items,
                "completed": t.completed_items,
                "failed": t.failed_items,
            }
            for t in tasks
        ]
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["任务ID", "类型", "状态", "总数", "已完成", "失败"])
        for t in tasks:
            writer.writerow(
                [
                    t.task_id,
                    t.task_type.value,
                    t.status.value,
                    t.total_items,
                    t.completed_items,
                    t.failed_items,
                ]
            )
    return 0
