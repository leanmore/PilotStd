"""启动期清理下载中断残留的 `.part` 半成品。"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger("pilotstd.download.part_cleanup")

DEFAULT_MAX_AGE_SECONDS = 3600  # 1 小时内的 .part 视为可能仍在下载，不动


def cleanup_stale_parts(save_root: str, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
                        now: float | None = None) -> int:
    """删除 `save_root` 下 mtime 早于 `max_age_seconds` 的 `*.part`，返回删除数量。"""
    if not save_root or not os.path.isdir(save_root):
        return 0
    now = time.time() if now is None else now
    cutoff = now - max_age_seconds
    removed = 0
    for dirpath, _dirs, files in os.walk(save_root):
        for name in files:
            if not name.endswith(".part"):
                continue
            path = os.path.join(dirpath, name)
            try:
                if os.path.getmtime(path) >= cutoff:
                    continue
                os.remove(path)
                removed += 1
                # i18n-allow: 内部日志/参数
                logger.warning("清理残留下载半成品: %s", path)
            except OSError as e:
                # i18n-allow: 内部日志/参数
                logger.warning("清理 .part 失败: %s (%s)", path, e)
    return removed
