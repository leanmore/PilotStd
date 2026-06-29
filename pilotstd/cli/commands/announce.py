# pilotstd/cli/commands/announce.py — announce + validity 子命令
import argparse

from pilotstd.cli.commands._shared import _make_manager

logger = __import__("logging").getLogger("pilotstd.cli")


def cmd_validity(args: argparse.Namespace) -> int:
    """执行时效性检查。"""
    from pilotstd.core.validity_checker import run_validity_check

    force = getattr(args, "force", False)
    print("正在执行时效性检查...")
    if force:
        print("--force 模式：无视分片限制，检查所有到期标准")

    result = run_validity_check(update_counters=not force)
    if not result.get("ok"):
        print(f"检查失败: {result.get('error', '未知错误')}")
        return 1

    checked = result.get("checked", 0)
    changed = result.get("changed", 0)
    if changed > 0:
        print(f"检查完成: {checked} 条已检查，{changed} 条状态变更")
    else:
        print(f"检查完成: {checked} 条已检查，无状态变更")
    return 0


def cmd_announce(args: argparse.Namespace) -> int:
    """检查公告更新，比对本地文件索引，输出命中结果。"""
    mgr = _make_manager(storage_root=getattr(args, "storage_root", None))
    std_type = getattr(args, "type", None)
    since = args.since or ""

    def _progress(cur: int, total: int, pid: str) -> None:
        logger.info("公告进度: %d/%d (pid=%s)", cur, total, pid)

    results = mgr.check_announcements_filtered(std_type=std_type, since_date=since, progress_callback=_progress)

    total_matched = 0
    for std_type_key, r in results.items():
        if "error" in r:
            print(f"[{std_type_key}] {r['error']}")
            continue
        print(f"[{std_type_key}] 公告抓取完成: 命中 {r.get('matched', 0)} 条, 更新 {r.get('updated', 0)} 条")
        total_matched += r.get("matched", 0)

    if total_matched == 0:
        print("没有新公告命中本地标准库。")
    return 0
