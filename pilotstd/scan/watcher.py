# pilotstd/scan/watcher.py — 增量文件监控（watchdog 事件驱动 + file_index 持久化）
# FileWatchHandler 处理创建/修改/删除/移动四类事件，自动更新索引
# FileWatcher 封装 Observer 生命周期，启动时先全量扫描再启动增量监控
"""基于 watchdog 的文件系统监控器，实现增量扫描。"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class FileWatchHandler(PatternMatchingEventHandler):
    """文件变更事件处理器：过滤 → 哈希 → 解析 → 更新 file_index。"""

    def __init__(
        self,
        file_index: Any,
        parser: Any,
        patterns: Optional[list[str]] = None,
        ignore_patterns: Optional[list[str]] = None,
        skip_dir_patterns: Optional[list[str]] = None,
    ) -> None:
        super().__init__(patterns=patterns, ignore_patterns=ignore_patterns, ignore_directories=True)
        self._file_index = file_index
        self._parser = parser
        self._skip_dir_patterns = skip_dir_patterns or []

    def _should_skip(self, path: str) -> bool:
        """检查路径是否在任何跳过目录下。"""
        norm = os.path.normpath(path).lower()
        for pat in self._skip_dir_patterns:
            if pat.lower() in norm.split(os.sep):
                return True
        return False

    # _handle_new_or_modified — 计算哈希 → 解析 → 更新索引，异常静默丢弃
    def _handle_new_or_modified(self, path: str) -> None:
        """处理文件创建或修改：计算哈希 → 解析文件名 → 更新索引。"""
        if self._should_skip(path):
            return
        try:
            from ..core.file_utils import hash_file_content

            file_hash = hash_file_content(path)
            parsed = self._parser.parse(os.path.basename(path))
            if parsed:
                self._file_index.upsert(
                    file_path=path,
                    logical_code=parsed.logical_code,
                    number=parsed.number,
                    year=parsed.year,
                    part=getattr(parsed, "part", None),
                    std_name=getattr(parsed, "std_name", ""),
                    file_hash=file_hash,
                    status=getattr(parsed, "effect_status", "") or "",
                    raw_number=getattr(parsed, "raw_number", ""),
                )
        except OSError:
            pass  # 文件被锁定或已删除
        except Exception:
            logger.debug("watcher 处理文件失败: %s", path, exc_info=True)

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle_new_or_modified(str(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle_new_or_modified(str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        """文件删除事件：从 file_index 中移除已删除的文件路径。"""
        if self._should_skip(str(event.src_path)):
            return
        try:
            self._file_index.remove(event.src_path)
        except Exception:
            pass

    def on_moved(self, event: FileSystemEvent) -> None:
        """文件移动/重命名：删除旧路径 → 按新路径重新索引。"""
        if self._should_skip(str(event.dest_path)):
            return
        try:
            self._file_index.remove(event.src_path)  # 先移除旧路径索引
            self._handle_new_or_modified(str(event.dest_path))  # 再按新路径重新索引
        except Exception:
            pass


class FileWatcher:
    """文件系统监控器：封装 watchdog Observer 生命周期和启动策略。"""

    def __init__(self, file_index: Any, parser: Any, config_manager: Any) -> None:
        self._file_index = file_index
        self._parser = parser
        self._observer: Any = None  # watchdog Observer 类型桩不完整
        self._watched_dirs: List[str] = []

        # 从配置获取过滤规则（与 FileScanner 保持一致）
        exts = config_manager.get("scan.extensions", [".pdf", ".doc", ".docx", ".txt"])
        self._patterns = [f"*{ext}" for ext in exts]
        self._skip_dir_names = config_manager.get("scan.skip_folders", ["过期作废"])
        self._skip_keywords = config_manager.get("scan.exclude_patterns", [])

    def start(self, root_paths: List[str]) -> None:
        """启动文件监控。先全量扫描填充索引，再启动 watcher。"""
        if self._observer is not None:
            return  # 已在运行

        self._watched_dirs = root_paths
        handler = FileWatchHandler(
            file_index=self._file_index,
            parser=self._parser,
            patterns=self._patterns,
            skip_dir_patterns=self._skip_dir_names,
        )
        self._observer = Observer()
        for path in root_paths:
            if os.path.isdir(path):
                self._observer.schedule(handler, path, recursive=True)  # 递归监控整个目录树
                logger.info("watcher 已启动: %s", path)
            else:
                logger.warning("watcher 跳过不存在的目录: %s", path)
        self._observer.start()

    def stop(self) -> None:
        """停止文件监控。"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("watcher 已停止")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
