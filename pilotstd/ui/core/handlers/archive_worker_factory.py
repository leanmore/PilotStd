# pilotstd/ui/core/handlers/archive_worker_factory.py
# ArchiveWorkerFactory — 封装 NormalizeWorker + ArchiveWorker 创建和信号连接。
#
# 将 on_normalize / on_save_to_folder 中的信号连接逻辑从 Handler 迁移至工厂。
"""ArchiveWorkerFactory — 封装 NormalizeWorker + ArchiveWorker 创建和信号连接。

将 on_normalize / on_save_to_folder 中的信号连接逻辑从 Handler 迁移至工厂。
"""

from __future__ import annotations

from typing import Any

from ...workers import ArchiveWorker, NormalizeWorker

# ── ArchiveCallbacks：回调集合数据类 ──


class ArchiveCallbacks:
    """归档/规范化 Worker 回调集合。"""

    __slots__ = ("on_batch_ready", "on_progress", "on_error", "on_finished")

    def __init__(
        self,
        on_batch_ready: Any,
        on_progress: Any,
        on_error: Any,
        on_finished: Any,
    ) -> None:
        self.on_batch_ready = on_batch_ready
        self.on_progress = on_progress
        self.on_error = on_error
        self.on_finished = on_finished


# ── ArchiveWorkerFactory：Worker 创建工厂 ──


class ArchiveWorkerFactory:
    """创建 NormalizeWorker / ArchiveWorker 并自动连接信号到回调。"""

    def __init__(self, mgr: Any, config: Any, pause_event: Any, parent: Any = None) -> None:
        self._mgr = mgr
        self._config = config
        self._pause_event = pause_event
        self._parent = parent

    # ── NormalizeWorker 创建 ──

    def create_normalize_worker(self, parsed_list: list[Any], callbacks: ArchiveCallbacks) -> NormalizeWorker:
        """创建规范化 Worker，连接 batch_ready/progress/error/finished 信号。"""
        worker = NormalizeWorker(
            self._mgr,
            parsed_list,
            pause_event=self._pause_event,
            parent=self._parent,
        )
        worker.batch_ready.connect(callbacks.on_batch_ready)
        worker.progress.connect(callbacks.on_progress)
        worker.error.connect(callbacks.on_error)
        worker.finished_signal.connect(callbacks.on_finished)
        return worker

    # ── ArchiveWorker 创建 ──

    def create_archive_worker(
        self,
        parsed_list: list[Any],
        root_dir: str,
        overwrite: bool,
        callbacks: ArchiveCallbacks,
    ) -> ArchiveWorker:
        """创建归档 Worker，连接 batch_ready/progress/error/finished 信号。"""
        worker = ArchiveWorker(
            self._mgr,
            parsed_list,
            root_dir,
            config=self._config,
            overwrite=overwrite,
            pause_event=self._pause_event,
            parent=self._parent,
        )
        worker.batch_ready.connect(callbacks.on_batch_ready)
        worker.progress.connect(callbacks.on_progress)
        worker.error.connect(callbacks.on_error)
        worker.finished_signal.connect(callbacks.on_finished)
        return worker
