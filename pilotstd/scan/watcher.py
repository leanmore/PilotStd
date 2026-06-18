# pilotstd/scan/watcher.py — 增量文件监控（watchdog 事件驱动 + file_index 持久化）
"""基于 watchdog 的文件系统监控器，实现增量扫描。"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class FileWatchHandler(PatternMatchingEventHandler):
    """文件变更事件处理器：过滤 → 哈希 → 解析 → 更新 file_index。"""

    def __init__(
        self,
        file_index,
        parser,
        patterns=None,
        ignore_patterns=None,
        skip_dir_patterns=None,
    ):
        super().__init__(
            patterns=patterns, ignore_patterns=ignore_patterns, ignore_directories=True
        )
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

    def _handle_new_or_modified(self, path: str):
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
                )
        except OSError:
            pass  # 文件被锁定或已删除
        except Exception:
            logger.debug("watcher 处理文件失败: %s", path, exc_info=True)

    def on_created(self, event: FileSystemEvent):
        self._handle_new_or_modified(event.src_path)

    def on_modified(self, event: FileSystemEvent):
        self._handle_new_or_modified(event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if self._should_skip(event.src_path):
            return
        try:
            self._file_index.remove(event.src_path)
        except Exception:
            pass

    def on_moved(self, event: FileSystemEvent):
        """文件移动/重命名：删除旧路径 → 按新路径重新索引。"""
        if self._should_skip(event.dest_path):
            return
        try:
            self._file_index.remove(event.src_path)
            self._handle_new_or_modified(event.dest_path)
        except Exception:
            pass


class FileWatcher:
    """文件系统监控器：封装 watchdog Observer 生命周期和启动策略。"""

    def __init__(self, file_index, parser, config_manager):
        self._file_index = file_index
        self._parser = parser
        self._observer: Optional[Observer] = None
        self._watched_dirs: List[str] = []

        # 从配置获取过滤规则（与 FileScanner 保持一致）
        exts = config_manager.get("scan.extensions", [".pdf", ".doc", ".docx", ".txt"])
        self._patterns = [f"*{ext}" for ext in exts]
        self._skip_dir_names = config_manager.get("scan.skip_folders", ["过期作废"])
        self._skip_keywords = config_manager.get("scan.exclude_patterns", [])

    def start(self, root_paths: List[str]):
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
                self._observer.schedule(handler, path, recursive=True)
                logger.info("watcher 已启动: %s", path)
            else:
                logger.warning("watcher 跳过不存在的目录: %s", path)
        self._observer.start()

    def stop(self):
        """停止文件监控。"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("watcher 已停止")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
