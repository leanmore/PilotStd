# pilotstd/core/logger.py
# 日志管理器：双通道（控制台+文件）、按大小轮转(256KB)、1个备份

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from typing import Optional

from .frozen import is_frozen

# 模块名缩写映射，便于日志筛选和阅读
_TAG_MAP = {
    "ui": "UI",
    "main_window": "UI",
    "scanner": "SCAN",
    "parser": "PARSE",
    "csres": "CSRES",
    "njbz365": "NJBZ",
    "std_gov": "STDGOV",
    "hbba": "HBBA",
    "iso_gov": "ISOGOV",
    "mock": "MOCK",
    "engine": "ENGINE",
    "rotator": "ROTATOR",
    "download": "DL",
    "session": "DL",
    "queue": "TASK",
    "task": "TASK",
    "mover": "ORG",
    "dir_builder": "ORG",
    "expire_handler": "ORG",
    "config": "CONFIG",
    "db": "DB",
    "logger": "LOG",
    "search_strategy": "MATCH",
    "cache": "CACHE",
    "stress": "STRESS",
    "stress_driver": "STRESS",
    "stress_logic": "STRESS",
    "stress_web": "STRESS",
}


class _TagFormatter(logging.Formatter):
    """带模块缩写的格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        tag = record.name
        # 取模块名最后一段
        last = record.name.rsplit(".", 1)[-1] if "." in record.name else record.name
        tag = _TAG_MAP.get(last, last.upper()[:6])
        record.tag = tag
        return super().format(record)


def _get_log_dir() -> str:
    """返回日志目录，开发环境用项目 logs/，打包后优先 exe 同级的 logs/。"""
    if is_frozen():
        exe_dir = os.path.dirname(sys.executable)
        log_dir = os.path.join(exe_dir, "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            return log_dir
        except OSError:
            appdata = os.path.join(
                os.environ.get("APPDATA", os.path.expanduser("~")), "PilotStd", "logs"
            )
            os.makedirs(appdata, exist_ok=True)
            return appdata
    return os.path.join(os.path.dirname(__file__), "..", "..", "logs")


class LoggerManager:
    """封装日志初始化，提供统一的 logger 获取入口。

    双通道输出：控制台(INFO) + 文件(DEBUG)。
    按 256KB 大小轮转，保留 1 个备份文件。
    """

    _instance: Optional["LoggerManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        log_dir: Optional[str] = None,
        level: int = logging.INFO,
        retain_days: int = 14,
    ) -> None:
        if log_dir is None:
            log_dir = _get_log_dir()
        self._log_dir = os.path.abspath(log_dir)
        os.makedirs(self._log_dir, exist_ok=True)

        self._level = level
        self._retain_days = retain_days

        # 文件日志 — 年份完整，便于跨年回溯
        file_fmt = _TagFormatter(
            "%(asctime)s [%(levelname).1s] %(tag)-6s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # 控制台日志
        console_fmt = _TagFormatter(
            "%(asctime)s [%(levelname).1s] %(tag)-6s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(self._console_handler(console_fmt))
        root.addHandler(self._file_handler("app.log", file_fmt))

        # 抑制第三方库日志噪音
        for noisy in ("urllib3", "requests", "charset_normalizer", "lxml", "PIL"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        self._cleanup_old_logs()
        LoggerManager._instance = self

    # ---- 公共 ----

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        if LoggerManager._instance is None:
            with LoggerManager._lock:
                if LoggerManager._instance is None:
                    LoggerManager(level=logging.DEBUG)
        return logging.getLogger(name)

    @staticmethod
    def set_level(level: int) -> None:
        logging.getLogger().setLevel(level)

    # ---- 内部 ----

    def _console_handler(self, fmt: logging.Formatter) -> logging.Handler:
        h = logging.StreamHandler()
        h.setLevel(self._level)
        h.setFormatter(fmt)
        return h

    def _file_handler(self, filename: str, fmt: logging.Formatter) -> logging.Handler:
        path = os.path.join(self._log_dir, filename)
        h = RotatingFileHandler(
            path,
            maxBytes=256 * 1024,
            backupCount=1,
            encoding="utf-8",
        )
        h.setLevel(logging.DEBUG)
        h.setFormatter(fmt)
        return h

    def _cleanup_old_logs(self) -> None:
        """轮转由 RotatingFileHandler 自动管理（backupCount=1），无需手动清理。"""
