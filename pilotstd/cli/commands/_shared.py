# pilotstd/cli/commands/_shared.py — 共享工具函数
import logging
from typing import Any

from pilotstd.core.config import ConfigManager

logger = logging.getLogger("pilotstd.cli")


def _make_manager(storage_root: Any = None, use_cache: bool = True) -> Any:
    """创建 StandardManager 实例——CLI 和测试的统一入口。"""
    from pilotstd.manager.facade import StandardManager

    cfg = ConfigManager()
    if storage_root:
        cfg.set("storage.root_dir", storage_root)
    if not use_cache:
        cfg.set("query.use_cache", False)
    return StandardManager(config=cfg)
