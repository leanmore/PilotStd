# pilotstd/cli/commands/__init__.py
# CLI 子命令入口 — 组装参数解析器并派发到各子命令模块

import argparse
import logging
import os
import sys

from ...core.logger import LoggerManager
from .announce import cmd_announce, cmd_validity
from .auto import cmd_auto
from .download import cmd_download
from .expire import cmd_expire
from .move import cmd_move
from .normalize import cmd_normalize
from .organize import cmd_organize
from .pending import cmd_pending
from .query import cmd_query
from .scan import cmd_scan
from .task import cmd_task

logger = logging.getLogger("pilotstd.cli")

# 公开导出（供外部直接引用子命令函数）
__all__ = [
    "cmd_announce",
    "cmd_auto",
    "cmd_download",
    "cmd_expire",
    "cmd_move",
    "cmd_normalize",
    "cmd_organize",
    "cmd_pending",
    "cmd_query",
    "cmd_scan",
    "cmd_task",
    "cmd_validity",
    "build_parser",
    "main",
]


def _add_core_subparsers(sub: argparse._SubParsersAction) -> None:
    """核心流程：扫描/查询/下载/归档。"""
    p = sub.add_parser("scan", help="扫描目录")
    p.add_argument("paths", nargs="+", help="要扫描的目录路径（支持多个）")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("query", help="查询标准有效性并分类")
    p.add_argument("--file", "-f", help="标准号列表文件")
    p.add_argument("--no-cache", action="store_true", help="跳过缓存")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("download", help="下载分类结果中的标准")
    p.add_argument("--file", "-f", help="标准号列表文件（每行一个），直接从文件读取下载，跳过查询队列")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("organize", help="规范化并归档到标准库")
    p.add_argument("--source", "-s", help="要归档的源目录（扫描后归档）")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=cmd_organize)


def _add_pipeline_subparsers(sub: argparse._SubParsersAction) -> None:
    """管线类：一键处理/待确认/规范化/公告/任务。"""
    p = sub.add_parser("auto", help="一键处理：扫描→查询→下载→归档")
    p.add_argument("path", help="要处理的目录路径")
    p.add_argument("--no-cache", action="store_true", help="跳过缓存")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=cmd_auto)

    p = sub.add_parser("pending", help="查看/导出待确认清单")
    p.add_argument("--output", "-o", help="导出 CSV 路径")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=cmd_pending)

    p = sub.add_parser("normalize", help="解析文件名并输出规范化格式（不移动）")
    p.add_argument("files", nargs="+", help="文件路径")
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=cmd_normalize)

    p = sub.add_parser("announce", help="检查公告更新")
    p.add_argument("--since", help="起始日期 YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.add_argument("--type", choices=["gb", "hb", "db"])
    p.set_defaults(func=cmd_announce)

    p = sub.add_parser("task", help="查看任务队列")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=cmd_task)


def _add_file_ops_subparsers(sub: argparse._SubParsersAction) -> None:
    """文件操作：移动/过期/时效性检查。"""
    p = sub.add_parser("move", help="移动文件到分类目录")
    p.add_argument("files", nargs="+", help="文件路径")
    p.add_argument("--root", "-r", help="标准库存放根目录")
    p.add_argument("--dry-run", action="store_true", help="预览模式")
    p.set_defaults(func=cmd_move)

    p = sub.add_parser("expire", help="移入过期作废目录")
    p.add_argument("files", nargs="+", help="文件路径")
    p.add_argument("--root", "-r", help="标准库存放根目录")
    p.set_defaults(func=cmd_expire)

    p = sub.add_parser("validity", help="执行时效性检查")
    p.add_argument("--force", "-f", action="store_true", help="强制执行（无视分片限制）")
    p.add_argument("--root", "-r", help="标准库存放根目录")
    p.set_defaults(func=cmd_validity)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilotstd", description="PilotStd CLI")
    parser.add_argument("--storage-root", "-r", help="标准库存放根目录")
    sub = parser.add_subparsers(dest="command")

    _add_core_subparsers(sub)
    _add_pipeline_subparsers(sub)
    _add_file_ops_subparsers(sub)

    return parser


def main() -> int:
    LoggerManager(level=logging.INFO)
    logger.info(
        "[CLI] 会话开始 PID=%d 命令=%s",
        os.getpid(),
        sys.argv[1] if len(sys.argv) > 1 else "?",
    )
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)  # type: ignore[no-any-return]


class CLI:
    """命令行入口适配类（向后兼容——包化前 CLI 类包含静态命令方法）。
    所有命令逻辑已提取到独立子模块，此处仅做静态方法转发。"""

    cmd_announce = staticmethod(cmd_announce)
    cmd_auto = staticmethod(cmd_auto)
    cmd_download = staticmethod(cmd_download)
    cmd_expire = staticmethod(cmd_expire)
    cmd_move = staticmethod(cmd_move)
    cmd_normalize = staticmethod(cmd_normalize)
    cmd_organize = staticmethod(cmd_organize)
    cmd_pending = staticmethod(cmd_pending)
    cmd_query = staticmethod(cmd_query)
    cmd_scan = staticmethod(cmd_scan)
    cmd_task = staticmethod(cmd_task)
    cmd_validity = staticmethod(cmd_validity)
