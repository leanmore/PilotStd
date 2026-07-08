# pilotstd/monitor/scheduler.py
"""文件监控调度器——管理 watchdog Observer 生命周期。"""

import logging
import os
import threading
import time
from typing import Any

from watchdog.observers import Observer

from .config import get_config, get_monitor_stats
from .handler import StandardFileHandler

logger = logging.getLogger(__name__)

_instance = None


def get_scheduler():
    global _instance
    if _instance is None:
        _instance = FileMonitorScheduler()
    return _instance


class FileMonitorScheduler:
    def __init__(self, manager: Any = None):
        self.observer: Observer | None = None
        self.handler: StandardFileHandler | None = None
        self.running = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._mgr = manager  # 依赖注入，避免 monitor→manager 反向导入

    def start(self):
        if self.running:
            return
        cfg = get_config()
        if not cfg.get("enabled", True):
            logger.info("[MONITOR] 已禁用，跳过")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="file-monitor")
        self._thread.start()
        logger.info("[MONITOR] 启动成功")

    def stop(self):
        self._stop.set()
        if self.observer:
            self.observer.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self.running = False
        logger.info("[MONITOR] 已停止")

    def _run(self):
        cfg = get_config()
        watch_path = cfg.get("watch_path", "/inbox")
        delay = cfg.get("delay_seconds", 5)
        recursive = cfg.get("recursive", True)

        os.makedirs(watch_path, exist_ok=True)

        self.handler = StandardFileHandler(callback=self._on_file, delay_seconds=delay)
        self.observer = Observer()
        self.observer.schedule(self.handler, watch_path, recursive=recursive)
        self.observer.start()
        self.running = True
        logger.info("[MONITOR] 监控 %s (recursive=%s delay=%ds)", watch_path, recursive, delay)

        try:
            while not self._stop.is_set():
                time.sleep(1)
        finally:
            self.observer.stop()
            self.observer.join()
            self.running = False

    def _on_file(self, path: str):
        cfg = get_config()
        if not cfg.get("auto_archive", True):
            logger.info("[MONITOR] 自动归档已禁用，跳过: %s", path)
            return

        stats = get_monitor_stats()
        stats.increment("processed")

        try:
            if self._mgr is None:
                # 兼容未注入 manager 的场景（自动降级）
                from pilotstd.manager.facade import StandardManager  # noqa: PLC0415

                self._mgr = StandardManager()
            mgr = self._mgr
            scanned = mgr.scan_directory(os.path.dirname(path))
            if scanned:
                logger.info("[MONITOR] 扫描完成: %d 条", len(scanned))
                stats.increment("success")
            else:
                logger.info("[MONITOR] 扫描完成: 0 条")
        except Exception as e:
            logger.error("[MONITOR] 处理失败: %s — %s", path, e)
            stats.increment("failed")

    def get_status(self) -> dict:
        cfg = get_config()
        today_stats = get_monitor_stats().get_today_stats()
        return {
            "running": self.running,
            "enabled": cfg.get("enabled", True),
            "watch_path": cfg.get("watch_path", "/inbox"),
            "delay_seconds": cfg.get("delay_seconds", 5),
            "last_processed": "",
            "processed_today": today_stats["processed"],
            "success_today": today_stats["success"],
            "failed_today": today_stats["failed"],
        }
