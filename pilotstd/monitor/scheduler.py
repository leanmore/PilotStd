# 模块：项目//调度器脚本
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


def _log_trace_id() -> str:
    """生成日志结构化上下文用的短随机追踪号（线程安全，无依赖）。"""
    import secrets

    return secrets.token_hex(4)

_instance = None


def resolve_monitor_config(cfg: dict | None = None) -> dict:
    """解析监控配置，支持环境变量覆盖。传入cfg时可纯函数运行，零I/O。

    .. note:: 可测试单元
       在测试中显式传入cfg以避免get_config()的I/O依赖。
    """
    if cfg is None:
        cfg = get_config()
    return {
        "watch_path": (
            os.environ.get("PILOTSTD_STORAGE_INBOX_DIR")
            or cfg.get("watch_path")
            or "/tmp/pilotstd-inbox"
        ),
        "delay_seconds": cfg.get("delay_seconds", 5),
        "recursive": cfg.get("recursive", True),
    }


def get_scheduler():
    """返回全局单例 FileMonitorScheduler 实例。"""
    global _instance
    if _instance is None:
        _instance = FileMonitorScheduler()
    return _instance


# 后台线程驱动，文件就绪后触发自动归档
# 全局单例模式，通过_调度器()获取，/管理生命周期
class FileMonitorScheduler:
    def __init__(self, manager: Any = None):
        self.observer: Observer | None = None  # type: ignore[valid-type]
        self.handler: StandardFileHandler | None = None
        self.running = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._mgr = manager  # 依赖注入，避免 monitor→manager 反向导入

    def start(self):
        """启动文件监控后台线程。"""
        if self.running:
            return
        cfg = get_config()
        if not cfg.get("enabled", True):
            # 批次4：禁用时跳过启动并记录结构化日志（running 保持 False）
            logger.info(
                "监控已禁用，跳过启动: trace_id=%s source_type=monitor_scheduler target_chat_id=-",
                _log_trace_id(),
            )
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="file-monitor")
        self._thread.start()
        logger.info("[MONITOR] 启动成功")

    def stop(self):
        """停止文件监控，等待后台线程退出并清理资源。"""
        self._stop.set()
        if self.observer:
            self.observer.stop()
        if self._thread:
            self._thread.join(timeout=5)
        self.running = False
        logger.info(
            "监控调度器已停止: trace_id=%s source_type=monitor_scheduler target_chat_id=-",
            _log_trace_id(),
        )

    def _run(self):
        """后台监控循环。

        .. note:: E2E范围
           配置解析通过resolve_monitor_config()测试。
           Observer生命周期+sleep循环需集成/E2E测试。
           参见：docs/testing/playbook.md §UI-layer skip rule #3
        """
        resolved = resolve_monitor_config()
        watch_path = resolved["watch_path"]
        delay = resolved["delay_seconds"]
        recursive = resolved["recursive"]

        source = ("env" if os.environ.get("PILOTSTD_STORAGE_INBOX_DIR")
                  else ("db" if get_config().get("watch_path") else "default"))
        logger.info("[MONITOR] watch_path=%s (source=%s)", watch_path, source)
        try:
            os.makedirs(watch_path, exist_ok=True)
        except OSError as e:
            logger.error("[MONITOR] 无法创建 watch_path=%s: %s — 文件监控已禁用", watch_path, e)
            return

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
        """文件稳定后触发：解析 → 归档 → 按**真实归档结果**计数。

        计数口径（技术债 #30）：`success` 必须是"真归档成功"，不能是"文件名解析出来了"。
        改前只调 `scan_directory`（仅解析、不搬文件、不写 `file_index`）却照记 success，
        现场出现 `processed_today=6 / success_today=6` 而 inbox 里 6 个文件一个都没入库
        → 面板显示健康、实际什么都没发生（`auto_archive` 开关形同虚设）。
        """
        cfg = get_config()
        if not cfg.get("auto_archive", True):
            logger.info("[MONITOR] 自动归档已禁用，跳过: %s", path)
            return

        stats = get_monitor_stats()
        stats.increment("processed")

        try:
            if self._mgr is None:
                # 兼容未注入管理器的场景（自动降级）
                from pilotstd.manager.facade import StandardManager  # noqa: PLC0415

                self._mgr = StandardManager()
            mgr = self._mgr
            source_root = os.path.dirname(path)
            scanned = mgr.scan_directory(source_root)
            if not scanned:
                logger.warning("[MONITOR] 未识别到标准号，未归档: %s", path)
                stats.increment("failed")
                return
            # 归档走**统一入口**（CLI/Web/UI 同一实现），不是第二套归档逻辑；
            # 与收藏链（#29）不重复：链路归档发生在下载返回后，本回调要等 5 秒稳定期且
            # handler 会先判 `os.path.exists`——文件已被链路搬走时回调根本不会触发。
            result = mgr.archive_standards(scanned, word_source_root=source_root)
            moved = int(result.get("moved", 0)) if isinstance(result, dict) else 0
            if moved:
                logger.info("[MONITOR] 归档完成: %d 条", moved)
                stats.increment("success")
            elif isinstance(result, dict) and result.get("failed", 0):
                logger.error("[MONITOR] 归档失败: %s — %s", path, result.get("details", []))
                stats.increment("failed")
            else:
                # 源文件已被移走/目标已存在/条目待确认 → 无搬移，不计成败
                logger.info("[MONITOR] 未搬移文件（跳过）: %s", path)
        except Exception as e:
            logger.error("[MONITOR] 处理失败: %s — %s", path, e)
            stats.increment("failed")

    def get_status(self) -> dict:
        """返回监控运行状态，包含运行标志、路径、今日统计等。"""
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
