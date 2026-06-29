# pilotstd/cli/commands/query.py — query 子命令
import argparse
import csv
import sys

from pilotstd.cli.commands._shared import _make_manager

logger = __import__("logging").getLogger("pilotstd.cli")


def cmd_query(args: argparse.Namespace) -> int:
    """查询标准有效性并分类。从 stdin 或 --file 读取标准号列表。"""
    mgr = _make_manager(
        storage_root=getattr(args, "storage_root", None),
        use_cache=not getattr(args, "no_cache", False),
    )

    numbers = []
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            numbers = [line.strip() for line in f if line.strip()]
    else:
        numbers = [line.strip() for line in sys.stdin if line.strip()]

    if not numbers:
        print("未提供标准号，使用 --file 参数或管道输入", file=sys.stderr)
        return 1

    parsed_list = []
    for num in numbers:
        info = mgr.parser.parse(num + ".pdf")
        if info:
            info.std_name = ""
            parsed_list.append(info)
        else:
            logger.warning("无法解析: %s", num)

    if not parsed_list:
        print("所有标准号均无法解析", file=sys.stderr)
        return 1

    _progress_last_log = [0.0]
    _progress_last_pct = [-1]

    def _progress(count: int, _total: int) -> None:
        pct = count * 100 // _total
        import time

        now = time.monotonic()
        if now - _progress_last_log[0] >= 15 or abs(pct - _progress_last_pct[0]) >= 10:
            logger.info("查询进度: %d/%d (%d%%)", count, _total, pct)
            _progress_last_log[0] = now
            _progress_last_pct[0] = pct

    results, stats = mgr.query(parsed_list, progress_callback=_progress)

    writer = csv.writer(sys.stdout)
    writer.writerow(["标准号", "标准名称", "状态", "匹配状态", "下一步", "来源站点", "是否采标"])
    for p, r in zip(parsed_list, results):
        writer.writerow(
            [
                p.get_full_number(),
                r.standard_name or p.std_name,
                r.status,
                getattr(r, "match_status", ""),
                p.next_action,
                getattr(r, "source_site", ""),
                "是" if getattr(r, "is_adopted", False) else "否",
            ]
        )

    s = mgr.get_stage_summary()
    print(
        f"\n查询: {stats.found} 找到, {stats.adopted_restricted} 采标",
        file=sys.stderr,
    )
    print(
        f"分类: download={s['download']} expire={s['expire']} pending={s['pending']}",
        file=sys.stderr,
    )
    return 0
