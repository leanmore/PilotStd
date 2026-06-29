# pilotstd/core/config/paths.py
# 目录/路径相关函数 — 从 config.py 拆分

import os
import sys
from typing import Any

from ..frozen import is_frozen


def _get_config_dir() -> str:
    """返回配置文件目录。"""
    if is_frozen():
        exe_dir = os.path.dirname(sys.executable)
        cfg_dir = os.path.join(exe_dir, "config")
        try:
            os.makedirs(cfg_dir, exist_ok=True)
            test = os.path.join(cfg_dir, ".write_test")
            with open(test, "w") as f:
                f.write("")
            os.remove(test)
            return cfg_dir
        except OSError:
            pass
        appdata = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PilotStd")
        os.makedirs(appdata, exist_ok=True)
        return appdata
    else:
        return os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")


def get_data_dir() -> str:
    """返回可写数据目录（数据库、缓存、下载文件等）。"""
    if is_frozen():
        exe_dir = os.path.dirname(sys.executable)
        data_dir = os.path.join(exe_dir, "data")
        try:
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
        except OSError:
            appdata = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PilotStd")
            os.makedirs(appdata, exist_ok=True)
            return appdata
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")


def get_db_path() -> str:
    """返回 SQLite 数据库完整路径。"""
    return os.path.join(get_data_dir(), "pilotstd.db")


def get_network_timeout(config: Any) -> int:
    """返回网络请求超时秒数（从配置读取，默认30）。"""
    return config.get("network.timeout", 30)  # type: ignore[no-any-return]


def get_library_root(config: Any) -> str:
    """返回标准库根目录路径。路径不存在时自动创建。"""
    import logging

    _log = logging.getLogger("pilotstd.config")
    root = os.environ.get("STANDARD_ROOT") or config.get("storage.root_dir", os.path.expanduser("~/标准"))
    root = os.path.abspath(os.path.normpath(root))
    if not os.path.exists(root):
        try:
            os.makedirs(root, exist_ok=True)
            _log.info("已创建库根目录: %s", root)
        except OSError as e:
            _log.error("无法创建库根目录 %s: %s", root, e)
    elif not os.access(root, os.W_OK):
        _log.error("库根目录不可写: %s", root)
    return root
