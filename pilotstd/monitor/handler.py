# pilotstd/monitor/handler.py
"""watchdog EventHandler——延迟 + 去重处理新文件。"""

import logging
import os
import threading
import time

from watchdog.events import FileSystemEventHandler

from .config import get_config

logger = logging.getLogger(__name__)


class StandardFileHandler(FileSystemEventHandler):
    """监控目录变化，在文件稳定后触发回调。"""

    def __init__(self, callback, delay_seconds: int = 5):
        super().__init__()
        self.callback = callback
        self.delay = delay_seconds
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._handle(event.dest_path)

    def _handle(self, path: str):
        """去重 + 延迟触发。"""
        if not self._should_handle(path):
            return

        with self._lock:
            if path in self._pending:
                return
            self._pending[path] = time.time()

        def delayed():
            time.sleep(self.delay)
            with self._lock:
                self._pending.pop(path, None)
            if os.path.exists(path):
                logger.info("[MONITOR] 检测到新文件: %s", os.path.basename(path))
                self.callback(path)

        t = threading.Timer(self.delay, delayed)
        t.daemon = True
        t.start()

    def _should_handle(self, path: str) -> bool:
        basename = os.path.basename(path)
        if basename.startswith("."):
            return False
        cfg = get_config()
        ext = os.path.splitext(path)[1].lower()
        patterns = cfg.get("file_patterns", [".pdf", ".docx", ".doc"])
        if patterns and ext not in patterns:
            return False
        for ig in cfg.get("ignore_patterns", ["~$", ".tmp", ".swp"]):
            if ig in basename:
                return False
        return True
