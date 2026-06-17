# pilotstd/cli/commands.py
# CLI 子命令：scan, query, download, organize, auto, normalize, move, expire, announce, task

import os
import sys
import json
import csv
import argparse
import logging

from ..core.config import ConfigManager, get_library_root
from ..core.logger import LoggerManager

logger = logging.getLogger("pilotstd.cli")


def _make_manager(storage_root=None, use_cache=True):
    """创建 StandardManager 实例——CLI 和测试的统一入口。"""
    from ..manager.facade import StandardManager
    cfg = ConfigManager()
    if storage_root:
        cfg.set("storage.root_dir", storage_root)
    if not use_cache:
        cfg.set("query.use_cache", False)
    return StandardManager(config=cfg)


class CLI:
    """命令行入口。扫描/查询/下载/归档 走 Manager；其余命令保持独立。"""

    def __init__(self):
        self.cfg = ConfigManager()
        LoggerManager(level=logging.INFO)

    # ── scan ────────────────────────────────────────────────────

    @staticmethod
    def cmd_scan(args):
        """扫描目录（支持多目录），输出解析结果。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        shallow = getattr(args, 'shallow', False)

        parsed = []
        for path in args.paths:
            parsed.extend(mgr.scan_directory(path, recursive=not shallow))

        if args.format == "json":
            data = [{"index": i + 1, "code": p.logical_code, "number": p.number,
                     "year": p.year, "part": p.part, "name": p.std_name,
                     "full_number": p.get_full_number()}
                    for i, p in enumerate(parsed)]
            json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        else:
            writer = csv.writer(sys.stdout)
            writer.writerow(["序号", "代号", "顺序号", "年份", "部分号", "标准名称", "完整编号"])
            for i, p in enumerate(parsed):
                writer.writerow([i + 1, p.logical_code, p.number, p.year,
                                 p.part or "", p.std_name, p.get_full_number()])
        return 0

    # ── query ───────────────────────────────────────────────────

    @staticmethod
    def cmd_query(args):
        """查询标准有效性并分类。从 stdin 或 --file 读取标准号列表。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None),
                            use_cache=not getattr(args, 'no_cache', False))

        # 读取标准号
        numbers = []
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                numbers = [line.strip() for line in f if line.strip()]
        else:
            numbers = [line.strip() for line in sys.stdin if line.strip()]

        if not numbers:
            print("未提供标准号，使用 --file 参数或管道输入", file=sys.stderr)
            return 1

        # 解析为标准信息
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

        # 查询（带进度汇报——终端 \r 行 + 日志定时落盘）
        total = len(parsed_list)
        _progress_last_log = [0.0]
        _progress_last_pct = [-1]

        def _progress(count: int, _total: int):
            pct = count * 100 // _total
            # 日志：每 15 秒或跨越 10% 阈值时写一条
            import time
            now = time.monotonic()
            if now - _progress_last_log[0] >= 15 or abs(pct - _progress_last_pct[0]) >= 10:
                logger.info("查询进度: %d/%d (%d%%)", count, _total, pct)
                _progress_last_log[0] = now
                _progress_last_pct[0] = pct
            else:
                msg = f"查询进度: {count}/{_total} ({pct}%)"
                print(f"\r  {msg}", end="", file=sys.stderr, flush=True)
                logger.debug(msg)

        results, stats = mgr.query(parsed_list, progress_callback=_progress)
        if total:
            print(file=sys.stderr)  # 进度行换行

        # 输出：含分类结果
        writer = csv.writer(sys.stdout)
        writer.writerow(["标准号", "标准名称", "状态", "匹配状态", "下一步", "来源站点", "是否采标"])
        for i, (p, r) in enumerate(zip(parsed_list, results)):
            writer.writerow([
                p.get_full_number(),
                r.standard_name or p.std_name,
                r.status,
                getattr(r, 'match_status', ''),
                p.next_action,
                getattr(r, 'source_site', ''),
                "是" if getattr(r, 'is_adopted', False) else "否",
            ])

        # 分类汇总
        s = mgr.get_stage_summary()
        print(f"\n查询: {stats.found} 找到, {stats.adopted_restricted} 采标", file=sys.stderr)
        print(f"分类: download={s['download']} expire={s['expire']} pending={s['pending']}",
              file=sys.stderr)
        return 0

    # ── download ────────────────────────────────────────────────

    @staticmethod
    def cmd_download(args):
        """下载标准。有 --file 时直接从文件读取标准号下载，否则从查询队列取。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))

        # 途径一：--file 直接下载，绕开查询队列
        if getattr(args, 'file', None):
            with open(args.file, "r", encoding="utf-8") as f:
                numbers = [line.strip() for line in f if line.strip()]
            if not numbers:
                print("文件中无标准号。", file=sys.stderr)
                return 1
            print(f"从文件读取 {len(numbers)} 条标准号，开始下载...", file=sys.stderr)
            tasks, stats = mgr.download_by_numbers(numbers)
            print(f"完成: {stats.success} 成功, {getattr(stats, 'skipped_exists', 0)} 已存在, "
                  f"{getattr(stats, 'skipped_adopted', 0)} 采标跳过, {stats.failed} 失败")
            for t in tasks:
                print(f"  {t.standard_number}: {t.status.value}"
                      + (f" -> {t.saved_path}" if t.saved_path else ""))
            return 0

        # 途径二：从查询队列取
        dl = mgr.get_stage_queue("download")
        if not dl:
            print("无待下载条目。请先执行 query 命令，或使用 -f 指定标准号列表文件。", file=sys.stderr)
            return 1

        print(f"待下载: {len(dl)} 条", file=sys.stderr)
        completed, stats = mgr.download()
        print(f"完成: {stats.success} 成功, {stats.skipped_exists} 已存在, "
              f"{getattr(stats, 'skipped_adopted', 0)} 采标跳过, {stats.failed} 失败")
        for t in completed:
            print(f"  {t.standard_number}: {t.status.value}"
                  + (f" -> {t.saved_path}" if t.saved_path else ""))
        return 0

    # ── organize ────────────────────────────────────────────────

    @staticmethod
    def cmd_organize(args):
        """规范化文件名并归档到标准库。--source 指定源目录时先扫描再归档。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        source = getattr(args, 'source', None)
        if source:
            parsed = mgr.scan_directory(source)
            logger.info("扫描完成: %d 条，开始归档...", len(parsed))
            result = mgr.organize(parsed, word_source_root=source)
        else:
            result = mgr.organize()
        print(json.dumps(result, ensure_ascii=False, indent=2) if getattr(args, 'format', None) == "json"
              else str(result))
        return 0

    # ── auto ────────────────────────────────────────────────────

    @staticmethod
    def cmd_auto(args):
        """一键处理：扫描→查询→下载→规范化→归档，全自动。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None),
                            use_cache=not getattr(args, 'no_cache', False))
        result = mgr.auto_run(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == "json"
              else str(result))
        return 0

    # ── pending ─────────────────────────────────────────────────

    @staticmethod
    def cmd_pending(args):
        """查看/导出待确认清单。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        items = mgr.get_pending_items()

        if args.format == "json":
            json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
        elif args.output:
            with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["标准编号", "文件名", "网站名称", "状态", "匹配状态", "来源站点"])
                for item in items:
                    w.writerow([item.get(k, "") for k in
                        ("standard_number","std_name","found_name",
                         "effect_status","match_status","source_site")])
            print(f"已导出 {len(items)} 条 → {args.output}")
        else:
            for item in items:
                print(f"  {item.get('standard_number','')} | {item.get('std_name','')}")
            print(f"\n共 {len(items)} 条待确认")
        return 0

    # ── announce ─────────────────────────────────────────────────

    @staticmethod
    def cmd_announce(args):
        """检查公告更新，比对本地文件索引，输出命中结果。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        std_type = getattr(args, 'type', None)
        since = args.since or ""

        def _progress(cur: int, total: int, pid: str):
            print(f"\r  公告进度: {cur}/{total}", end="", file=sys.stderr, flush=True)

        results = mgr.check_announcements_filtered(
            std_type=std_type, since_date=since, progress_callback=_progress)
        if results:
            print(file=sys.stderr)  # 进度行换行

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

    # ── task ─────────────────────────────────────────────────────

    @staticmethod
    def cmd_task(args):
        """查看任务队列状态。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        tasks = mgr.task_queue.list_all(limit=args.limit)
        if not tasks:
            print("暂无任务记录。")
            return 0

        if args.format == "json":
            data = [{"task_id": t.task_id, "type": t.task_type.value,
                     "status": t.status.value, "total": t.total_items,
                     "completed": t.completed_items, "failed": t.failed_items}
                    for t in tasks]
            json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        else:
            writer = csv.writer(sys.stdout)
            writer.writerow(["任务ID", "类型", "状态", "总数", "已完成", "失败"])
            for t in tasks:
                writer.writerow([t.task_id, t.task_type.value, t.status.value,
                                 t.total_items, t.completed_items, t.failed_items])
        return 0

    # ── normalize ────────────────────────────────────────────────

    @staticmethod
    def cmd_normalize(args):
        """解析文件名并输出规范化格式，不移动文件。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        results = mgr.normalize_files(args.files)

        if args.format == "json":
            json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
        else:
            writer = csv.writer(sys.stdout)
            writer.writerow(["源文件", "代号", "顺序号", "年份", "规范化名称", "目标文件夹"])
            for r in results:
                writer.writerow([r["source"], r["logical_code"], r["number"],
                                 r["year"], r["normalized"], r["folder"]])
        return 0

    # ── move ────────────────────────────────────────────────────

    @staticmethod
    def cmd_move(args):
        """将标准文件移动到分类目录。支持 --dry-run 预览。"""
        if args.dry_run:
            mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
            root = get_library_root(mgr.cfg)
            info_list = mgr.normalize_files(args.files)
            print(f"[预览模式] 将移动 {len(info_list)} 个文件:\n")
            for item in info_list:
                print(f"  {os.path.basename(item['source'])} -> {os.path.join(root, item['folder'], item['normalized'])}")
            return 0

        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        result = mgr.organize_files(args.files)
        for detail in result.get("details", []):
            print(f"  {detail}")
        moved = result.get("moved", 0)
        print(f"\n移动完成: {moved}/{len(args.files)}")
        return 0 if moved > 0 else 1

    # ── expire ──────────────────────────────────────────────────

    @staticmethod
    def cmd_expire(args):
        """将过期标准文件移入 过期作废/ 目录。"""
        mgr = _make_manager(storage_root=getattr(args, 'storage_root', None))
        result = mgr.expire_files(args.files)
        print(f"已移动: {result['moved']}, 失败: {result['failed']}")
        for detail in result["details"]:
            print(f"  {detail}")
        return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="pilotstd", description="PilotStd CLI")
    parser.add_argument("--storage-root", "-r", help="标准库存放根目录")
    sub = parser.add_subparsers(dest="command")

    # scan
    p = sub.add_parser("scan", help="扫描目录")
    p.add_argument("paths", nargs="+", help="要扫描的目录路径（支持多个）")
    p.add_argument("--shallow", action="store_true", help="仅扫描顶层")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=CLI.cmd_scan)

    # query
    p = sub.add_parser("query", help="查询标准有效性并分类")
    p.add_argument("--file", "-f", help="标准号列表文件")
    p.add_argument("--no-cache", action="store_true", help="跳过缓存")
    p.set_defaults(func=CLI.cmd_query)

    # download
    p = sub.add_parser("download", help="下载分类结果中的标准")
    p.add_argument("--file", "-f", help="标准号列表文件（每行一个），直接从文件读取下载，跳过查询队列")
    p.set_defaults(func=CLI.cmd_download)

    # organize
    p = sub.add_parser("organize", help="规范化并归档到标准库")
    p.add_argument("--source", "-s", help="要归档的源目录（扫描后归档）")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=CLI.cmd_organize)

    # auto
    p = sub.add_parser("auto", help="一键处理：扫描→查询→下载→归档")
    p.add_argument("path", help="要处理的目录路径")
    p.add_argument("--no-cache", action="store_true", help="跳过缓存")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=CLI.cmd_auto)

    # pending
    p = sub.add_parser("pending", help="查看/导出待确认清单")
    p.add_argument("--output", "-o", help="导出 CSV 路径")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=CLI.cmd_pending)

    # normalize
    p = sub.add_parser("normalize", help="解析文件名并输出规范化格式（不移动）")
    p.add_argument("files", nargs="+", help="文件路径")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=CLI.cmd_normalize)

    # announce
    p = sub.add_parser("announce", help="检查公告更新")
    p.add_argument("--since", help="起始日期 YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.add_argument("--type", choices=["gb", "hb", "db"])
    p.set_defaults(func=CLI.cmd_announce)

    # task
    p = sub.add_parser("task", help="查看任务队列")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=CLI.cmd_task)

    # move
    p = sub.add_parser("move", help="移动文件到分类目录")
    p.add_argument("files", nargs="+", help="文件路径")
    p.add_argument("--root", "-r", help="标准库存放根目录")
    p.add_argument("--dry-run", action="store_true", help="预览模式")
    p.set_defaults(func=CLI.cmd_move)

    # expire
    p = sub.add_parser("expire", help="移入过期作废目录")
    p.add_argument("files", nargs="+", help="文件路径")
    p.add_argument("--root", "-r", help="标准库存放根目录")
    p.set_defaults(func=CLI.cmd_expire)

    return parser


def main():
    LoggerManager(level=logging.INFO)  # CLI 入口统一初始化日志
    logger.info("[CLI] 会话开始 PID=%d 命令=%s", os.getpid(), sys.argv[1] if len(sys.argv) > 1 else "?")
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
