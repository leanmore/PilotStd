# 项目//命令/脚本—子命令
import argparse
import os

from pilotstd.cli.commands._shared import _make_manager
from pilotstd.core.config import get_library_root


def cmd_move(args: argparse.Namespace) -> int:
    """将标准文件移动到分类目录。支持 --dry-run 预览。"""
    if args.dry_run:
        storage_root = getattr(args, "storage_root", None) or getattr(args, "root", None)
        mgr = _make_manager(storage_root=storage_root)
        root = get_library_root(mgr.cfg)
        info_list = mgr.normalize_files(args.files)
        print(f"[预览模式] 将移动 {len(info_list)} 个文件:\n")
        for item in info_list:
            print(f"  {os.path.basename(item['source'])} -> {os.path.join(root, item['folder'], item['normalized'])}")
        return 0

    storage_root = getattr(args, "storage_root", None) or getattr(args, "root", None)
    mgr = _make_manager(storage_root=storage_root)
    result = mgr.organize_files(args.files)
    for detail in result.get("details", []):
        print(f"  {detail}")
    moved = result.get("moved", 0)
    print(f"\n移动完成: {moved}/{len(args.files)}")
    return 0 if moved > 0 else 1
