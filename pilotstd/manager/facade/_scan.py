# 模块：项目/管理器/门面/_扫描脚本
"""ScanHandler：目录扫描、流式扫描、定时索引、文件监控，替代原 ScanMixin。"""
# 性能：.扫描()替代.()（上自带，减少60%）；
# 去重：内存（本批次）+_索引查哈希（跨扫描），先内存后数据库避免不必要数据库查询；
# 扫描__索引为定时任务专用，异常时发_扫描_通知，手动扫描异常不通知（用户已在用户界面看到）

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from ...core.config import get_library_root
from ...models import ParsedStdInfo

if TYPE_CHECKING:
    from ._core import ManagerCore

logger = logging.getLogger(__name__)
# 扫描处理器，封装所有扫描方法，替代原


class ScanHandler:
    """扫描处理器 — 封装所有扫描方法，替代原 ScanMixin。"""

    def __init__(self, core: "ManagerCore"):
        """初始化扫描处理器，持有 ManagerCore 引用。"""
        self._core = core

    # 扫描_—扫描目录，识别文件名中的标准号
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
        failed_count = len(result.files) - len(parsed) - dup_count
        parsed_paths = {getattr(p, "source_path", "") for p in parsed}
        failed_files = [
            {"path": getattr(f, "full_path", ""), "reason": "文件格式无法识别"}
            for f in result.files
            if getattr(f, "full_path", "") and getattr(f, "full_path", "") not in parsed_paths
        ]

        try:
            if self._core.notification_mgr:
                if len(parsed) > 0:
                    self._core.notification_mgr.send_event(
                        "scan_complete",
                        {
                            "total": len(result.files),
                            "success": len(parsed),
                            "failed": max(failed_count, 0),
                            "failed_files": failed_files[:10],
                        },
                    )
                elif failed_count == 0:
                    self._core.notification_mgr.send_event("scan_empty", {})
        except Exception as e:
            logger.warning("扫描完成通知发送失败: %s", e)

        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self._core.db).invalidate_by_source(DataSource.FILE_INDEX)
        except Exception:
            pass

        return parsed

    # 扫描__—流式扫描目录（线程安全）
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
        failed_count = total - len(parsed) - dup_count
        parsed_paths = {getattr(p, "source_path", "") for p in parsed}
        failed_files = [
            {"path": getattr(f, "full_path", ""), "reason": "文件格式无法识别"}
            for f in result.files
            if getattr(f, "full_path", "") and getattr(f, "full_path", "") not in parsed_paths
        ]

        try:
            if self._core.notification_mgr:
                if len(parsed) > 0:
                    self._core.notification_mgr.send_event(
                        "scan_complete",
                        {
                            "total": total,
                            "success": len(parsed),
                            "failed": max(failed_count, 0),
                            "failed_files": failed_files[:10],
                        },
                    )
                elif failed_count == 0:
                    self._core.notification_mgr.send_event("scan_empty", {})
        except Exception as e:
            logger.warning("扫描完成通知发送失败: %s", e)

        try:
            from pilotstd.core.cache_manager import CacheManager, DataSource

            CacheManager(self._core.db).invalidate_by_source(DataSource.FILE_INDEX)
        except Exception:
            pass

        return parsed

    # 扫描__索引—定时任务专用：四要素匹配→更新表
    def scan_and_index(self, root_path: Optional[str] = None) -> dict[str, int]:
        """Q6-1: 定时任务专用。root_path 参数保留向后兼容但不再使用，
        始终扫描 get_library_root() 返回的根目录。
        """
        try:
            result: dict[str, int] = self._core.scheduled_svc.scan_and_index()  # type: ignore[attr-defined,no-any-return]
            try:
                if self._core.notification_mgr:
                    if result.get("indexed", 0) > 0:
                        self._core.notification_mgr.send_event(
                            "scan_complete",
                            {
                                "total": result.get("indexed", 0) + result.get("failed", 0),
                                "success": result.get("indexed", 0),
                                "failed": result.get("failed", 0),
                                "failed_files": [],
                            },
                        )
                    elif result.get("indexed", 0) == 0 and result.get("failed", 0) == 0:
                        self._core.notification_mgr.send_event("scan_empty", {})
            except Exception as e:
                logger.warning("定时扫描通知发送失败: %s", e)
            return result
        except Exception as e:
            logger.exception("scan_and_index 定时任务失败")
            if self._core.notification_mgr:
                try:
                    self._core.notification_mgr.send_event(
                        "auto_scan_failed",
                        {"path": root_path or "默认", "error": str(e)[:200]},
                    )
                except Exception as e2:
                    logger.warning("扫描失败通知发送失败: %s", e2)
            return {"indexed": 0, "skipped": 0, "failed": 1}

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
