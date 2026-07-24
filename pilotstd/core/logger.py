# pilotstd/core/logger.py
# 日志管理器：双通道（控制台+文件）、按大小轮转(256KB)、1个备份
# 文件通道使用 QueueHandler + QueueListener 架构：
#   - 业务线程写 QueueHandler（非阻塞入队）
#   - 专用 QueueListener 线程持有 RotatingFileHandler 执行 os.rename
#   - 彻底消除 Windows 下日志滚动 PermissionError

import atexit
import io
import logging
import logging.handlers
import os
import sys
import threading
from queue import Queue
from typing import Optional

from .frozen import is_frozen

# 模块名缩写映射，便于日志筛选和阅读。
# 未列出的模块自动使用 last.upper()[:6] 作为标签（见 _TagFormatter.format()），
# 日志不会丢失。此处仅覆盖需要"更短可读标签"的历史模块，非适配器注册列表。
# 新增适配器无需修改此映射——自动获得模块名前6字符大写作为标签。
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
    """带模块缩写的格式化器，标签通过 i18n 运行时翻译。"""

    def format(self, record: logging.LogRecord) -> str:
        last = record.name.rsplit(".", 1)[-1] if "." in record.name else record.name
        tag = _TAG_MAP.get(last, last.upper()[:6])
        # 运行时翻译：根据当前语言设置动态翻译标签
        from pilotstd.i18n import _ as _i18n

        record.tag = _i18n(f"log.{tag}")
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
            appdata = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PilotStd", "logs")
            os.makedirs(appdata, exist_ok=True)
            return appdata
    return os.path.join(os.path.dirname(__file__), "..", "..", "logs")


class LoggerManager:
    """封装日志初始化，提供统一的 logger 获取入口。

    三通道输出：控制台(INFO) + 文件队列(DEBUG → QueueListener 专用线程落盘)。
    按 256KB 大小轮转，保留 1 个备份文件。
    文件通道使用 QueueHandler 架构消除 Windows 日志滚动 PermissionError。
    """

    _instance: Optional["LoggerManager"] = None
    _lock: threading.Lock = threading.Lock()
    _listener: Optional[logging.handlers.QueueListener] = None

    def __init__(
        self,
        log_dir: Optional[str] = None,
        level: int = logging.INFO,
        retain_days: int = 14,
    ) -> None:
        # 防止重复初始化：get_logger 和入口点可能先后调用 __init__
        if LoggerManager._instance is not None:
            return
        if log_dir is None:
            log_dir = _get_log_dir()
        # 绝对路径，防止后续 os.chdir 导致日志路径漂移
        self._log_dir = os.path.abspath(log_dir)
        os.makedirs(self._log_dir, exist_ok=True)

        self._level = level
        self._retain_days = retain_days

        # 文件日志 — 年份完整，便于跨年回溯
        file_fmt = _TagFormatter(
            "%(asctime)s [%(levelname).1s] %(tag)-6s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # 控制台日志 — 同上格式，INFO 级别
        console_fmt = _TagFormatter(
            "%(asctime)s [%(levelname).1s] %(tag)-6s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root = logging.getLogger()
        root.setLevel(level)
        # 控制台 handler：仅在有效终端环境下启用（PyInstaller -w 模式跳过）
        if self._console_available():
            root.addHandler(self._console_handler(console_fmt))

        # 文件 handler 通过 QueueListener 专用线程持有，消除 Windows os.rename 并发冲突
        file_handler = self._file_handler("app.log", file_fmt)
        # Queue(-1) 无限队列确保高并发时不丢日志
        log_queue: Queue = Queue(-1)
        root.addHandler(logging.handlers.QueueHandler(log_queue))
        LoggerManager._listener = logging.handlers.QueueListener(log_queue, file_handler)
        LoggerManager._listener.start()
        # 注册 atexit 钩子确保进程退出时 listener 优雅停止
        atexit.register(self._stop_listener)

        # 抑制第三方库日志噪音，避免日志文件被无意义信息淹没
        for noisy in ("urllib3", "requests", "charset_normalizer", "lxml", "PIL"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        self._cleanup_old_logs()
        LoggerManager._instance = self

    # ---- 公共 ----

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """获取指定名称的 logger，自动确保 LoggerManager 已初始化。"""
        if LoggerManager._instance is None:
            with LoggerManager._lock:
                if LoggerManager._instance is None:
                    LoggerManager(level=logging.DEBUG)
        return logging.getLogger(name)

    @staticmethod
    def set_level(level: int) -> None:
        """设置根 logger 的日志级别（全局生效）。"""
        logging.getLogger().setLevel(level)

    # ---- 内部 ----

    def _console_handler(self, fmt: logging.Formatter) -> logging.Handler:
        h = logging.StreamHandler()
        h.setLevel(self._level)
        h.setFormatter(fmt)
        return h

    @staticmethod
    def _console_available() -> bool:
        """检查是否有可用控制台——PyInstaller -w 模式下返回 False。"""
        if not sys.stderr or not sys.stdout:
            return False
        # --noconsole 打包后流无 fileno，StreamHandler 会崩溃
        for stream in (sys.stderr, sys.stdout):
            try:
                stream.fileno()
            except (io.UnsupportedOperation, AttributeError, OSError):
                return False
        return True

    def _file_handler(self, filename: str, fmt: logging.Formatter) -> logging.Handler:
        """创建按大小轮转的文件 handler（256KB/1备份）。"""
        path = os.path.join(self._log_dir, filename)
        # maxBytes=512KB：单文件可控，便于 grep 和跨平台传输
        # backupCount=10：保留 10 个历史备份，总占用 ≤ 5.5MB
        h = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=512 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
        # 文件通道 DEBUG 级别，保留完整调试信息
        h.setLevel(logging.DEBUG)
        h.setFormatter(fmt)
        return h

    def _stop_listener(self) -> None:
        """安全停止 QueueListener，空值保护。"""
        listener = LoggerManager._listener
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def _cleanup_old_logs(self) -> None:
        """轮转由 RotatingFileHandler 自动管理（backupCount=1），无需手动清理。"""
