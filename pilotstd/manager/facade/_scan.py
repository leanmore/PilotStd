# pilotstd/manager/facade/_scan.py
"""ScanHandler：目录扫描、流式扫描、定时索引、文件监控，替代原 ScanMixin。"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from ...core.config import get_library_root
from ...models import ParsedStdInfo

if TYPE_CHECKING:
    from ._core import ManagerCore

logger = logging.getLogger(__name__)
# ScanHandler — 扫描处理器，封装所有扫描方法，替代原 ScanMixin


class ScanHandler:
    """扫描处理器 — 封装所有扫描方法，替代原 ScanMixin。"""

    def __init__(self, core: "ManagerCore"):
        """初始化扫描处理器，持有 ManagerCore 引用。"""
        self._core = core

    # scan_directory — 扫描目录，识别文件名中的标准号
    def scan_directory(self, root_path: str) -> list[ParsedStdInfo]:
        """扫描目录，识别文件名中的标准号。"""
        result = self._core.scanner.scan([root_path])
        self._core.last_skipped_dirs = result.skipped_dirs
        self._core.scanner._seen_hashes.clear()

        parsed: list[ParsedStdInfo] = []
        seen_std_numbers = set()
        dup_count = 0

        for f in result.files:
            info = self._core.parser.parse(f.filename)
            if info:
                key = (info.logical_code, info.number, info.year, info.part)
                if key not in seen_std_numbers:
                    seen_std_numbers.add(key)
                    info.source_path = f.full_path
                    parsed.append(info)
                else:
                    dup_count += 1

        if dup_count > 0:
            logger.info("扫描去重: %d 条重复标准号已合并", dup_count)

        ext_count = {"pdf": 0, "doc": 0, "docx": 0, "other": 0}
        for p in result.files:
            src = getattr(p, "full_path", "")
            ext = os.path.splitext(src)[1].lower().lstrip(".")
            ext_count[ext if ext in ext_count else "other"] += 1
        result.ext_stats = ext_count  # type: ignore[attr-defined]

        self._core.parsed_results = parsed
        logger.info("扫描完成: %d/%d 识别成功", len(parsed), len(result.files))

        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self._core.db).invalidate_by_source(DataSource.FILE_INDEX)
        except Exception:
            pass

        return parsed

    # scan_directory_stream — 流式扫描目录（线程安全）
    def scan_directory_stream(
        self,
        root_path: str,
        on_progress: Any = None,
        on_batch: Any = None,
    ) -> list[ParsedStdInfo]:
        """流式扫描目录（线程安全）。"""
        result = self._core.scanner.scan([root_path])
        self._core.last_skipped_dirs = result.skipped_dirs

        parsed: list[ParsedStdInfo] = []
        seen_std_numbers = set()
        dup_count = 0
        total = len(result.files)
        batch: list[tuple[int, ParsedStdInfo]] = []

        for i, f in enumerate(result.files):
            info = self._core.parser.parse(f.filename)
            if info:
                key = (info.logical_code, info.number, info.year, info.part)
                if key not in seen_std_numbers:
                    seen_std_numbers.add(key)
                    info.source_path = f.full_path
                    parsed.append(info)
                    batch.append((i + 1, info))
                else:
                    dup_count += 1

            if on_batch and len(batch) >= 20:
                on_batch(batch)
                batch = []
            if on_progress:
                on_progress(i + 1, total)

        if on_batch and batch:
            on_batch(batch)

        if dup_count > 0:
            logger.info("扫描去重: %d 条重复标准号已合并", dup_count)

        ext_count = {"pdf": 0, "doc": 0, "docx": 0, "other": 0}
        for p in result.files:
            src = getattr(p, "full_path", "")
            ext = os.path.splitext(src)[1].lower().lstrip(".")
            ext_count[ext if ext in ext_count else "other"] += 1
        result.ext_stats = ext_count  # type: ignore[attr-defined]

        self._core.parsed_results = parsed
        logger.info("扫描完成: %d/%d 识别成功", len(parsed), total)

        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self._core.db).invalidate_by_source(DataSource.FILE_INDEX)
        except Exception:
            pass

        return parsed

    # scan_and_index — 定时任务专用：扫描目录 → 解析 → 写入 file_index
    def scan_and_index(self, root_path: Optional[str] = None) -> int:
        """定时任务专用：扫描目录 → 解析 → 写入 file_index。"""
        try:
            return self._core.scheduled_svc.scan_and_index(root_path)  # type: ignore[no-any-return]
        except Exception as e:
            logger.exception("scan_and_index 定时任务失败")
            if self._core.notification_mgr:
                try:
                    self._core.notification_mgr.send_event(
                        "auto_scan_failed",
                        {"path": root_path or "默认", "error": str(e)[:200]},
                    )
                except Exception:
                    pass
            return 0

    def start_watching(self, root_paths: Optional[list[str]] = None) -> None:
        """启动增量文件监控。需安装 watchdog 包。"""
        try:
            if self._core._file_watcher is None:
                paths = root_paths or [get_library_root(self._core.cfg)]
                from ...scan.watcher import FileWatcher

                self._core._file_watcher = FileWatcher(self._core.file_index, self._core.parser, self._core.cfg)
                self._core._file_watcher.start(paths)  # type: ignore[attr-defined]
                logger.info("增量文件监控已启动: %s", paths)
        except ImportError:
            logger.warning("watchdog 未安装，跳过增量监控")
        except Exception:
            logger.warning("启动文件监控失败", exc_info=True)

    def stop_watching(self) -> None:
        """停止增量文件监控。"""
        if self._core._file_watcher:
            self._core._file_watcher.stop()
            self._core._file_watcher = None

    def scan_stream(
        self,
        root_path: str,
        on_progress: Any = None,
        on_batch: Any = None,
    ) -> list[ParsedStdInfo]:
        """流式扫描目录（别名，保持命名一致性）。

        委托 scan_directory_stream，不重写逻辑。
        """
        return self.scan_directory_stream(root_path, on_progress, on_batch)
