# pilotstd/cli/commands/download.py — download 子命令
import argparse
import sys

from pilotstd.cli.commands._shared import _make_manager


def cmd_download(args: argparse.Namespace) -> int:
    """下载标准。有 --file 时直接从文件读取标准号下载，否则从查询队列取。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))

    if getattr(args, "file", None):
        with open(args.file, "r", encoding="utf-8") as f:
            numbers = [line.strip() for line in f if line.strip()]
        if not numbers:
            print("文件中无标准号。", file=sys.stderr)
            return 1
        print(f"从文件读取 {len(numbers)} 条标准号，开始下载...", file=sys.stderr)
        tasks, stats = mgr.download_by_numbers(numbers)
        print(
            f"完成: {stats.success} 成功, {getattr(stats, 'skipped_exists', 0)} 已存在, "
            f"{getattr(stats, 'skipped_adopted', 0)} 采标跳过, {stats.failed} 失败"
        )
        for t in tasks:
            print(f"  {t.standard_number}: {t.status.value}" + (f" -> {t.saved_path}" if t.saved_path else ""))
        return 0

    dl = mgr.get_stage_queue("download")
    if not dl:
        print(
            "无待下载条目。请先执行 query 命令，或使用 -f 指定标准号列表文件。",
            file=sys.stderr,
        )
        return 1

    print(f"待下载: {len(dl)} 条", file=sys.stderr)
    completed, stats = mgr.download()
    print(
        f"完成: {stats.success} 成功, {stats.skipped_exists} 已存在, "
        f"{getattr(stats, 'skipped_adopted', 0)} 采标跳过, {stats.failed} 失败"
    )
    for t in completed:
        print(f"  {t.standard_number}: {t.status.value}" + (f" -> {t.saved_path}" if t.saved_path else ""))
    return 0
