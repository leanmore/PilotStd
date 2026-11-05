"""启动期归档对账：修复“文件已移动、file_index 未更新”的悬空路径，清理过期目录孤儿。

背景：搬运 = os.replace（文件系统） + UPDATE file_index（数据库）两步，强杀可能停在中间
（2026-11-05 kill -9 演练：1 条悬空路径 + 1 个孤儿文件）。启动时对账是最终一致性的兜底。
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("pilotstd.core.archive_reconcile")


def _norm(path: str) -> str:
    """统一路径比较口径（Windows 大小写不敏感）。"""
    return os.path.normcase(os.path.abspath(path))


def reconcile_archive(
    db: Any,
    root_dir: str,
    # i18n-allow: 内部日志/参数
    expire_folder: str = "过期作废",
    recycle_subdir: str = ".recycle/expired_orphans",
    now: float | None = None,
) -> dict[str, int]:
    """对账 file_index 与磁盘归档目录，返回统计。

    1. 路径不存在 → 在“过期作废”目录按同名文件回填；
    2. 仍找不到 → WARNING（文件彻底丢失）；
    3. 过期目录中不在 file_index 的文件 → 移入回收站并记录。
    """
    now = time.time() if now is None else now
    root = Path(root_dir)
    expire_dir = root / expire_folder
    recycle_root = root / recycle_subdir / time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
    stats = {"checked": 0, "repaired": 0, "missing": 0, "orphans": 0}

    if not root.exists():
        # i18n-allow: 内部日志/参数
        logger.info("归档对账跳过：根目录不存在 %s", root)
        return stats

    rows = db.fetchall("SELECT id, file_path FROM file_index")
    referenced: set[str] = set()
    for row in rows:
        stats["checked"] += 1
        path = str(row["file_path"] or "")
        if not path:
            continue
        referenced.add(_norm(path))
        if os.path.exists(path):
            continue
        name = os.path.basename(path)
        candidates = sorted(expire_dir.rglob(name)) if expire_dir.exists() else []
        if candidates:
            new_path = str(candidates[0])
            db.execute("UPDATE file_index SET file_path=? WHERE id=?", (new_path, row["id"]))
            referenced.discard(_norm(path))
            referenced.add(_norm(new_path))
            stats["repaired"] += 1
            # i18n-allow: 内部日志/参数
            logger.warning("归档对账修复悬空路径: %s -> %s", path, new_path)
        else:
            stats["missing"] += 1
            # i18n-allow: 内部日志/参数
            logger.warning("归档对账发现文件丢失（无法回填）: %s", path)

    if expire_dir.exists():
        for item in expire_dir.rglob("*"):
            if not item.is_file():
                continue
            if _norm(str(item)) in referenced:
                continue
            rel = item.relative_to(expire_dir)
            dest = recycle_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(dest))
            stats["orphans"] += 1
            # i18n-allow: 内部日志/参数
            logger.warning("归档对账清理孤儿文件: %s -> %s", item, dest)

    return stats
