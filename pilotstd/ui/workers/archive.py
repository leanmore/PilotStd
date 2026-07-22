# pilotstd/ui/workers/archive.py — ArchiveWorker，从 workers.py 拆分
#
# 后台归档线程：文件移动 + 磁盘空间检查 + 断点续做。

import logging
import os
import shutil
import time as _time
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ...core.file_utils import make_standard_filename
from ...organizer.industry_lookup import get_folder_name
from ._common import _WORKER_BATCH_SIZE, _WORKER_FLUSH_INTERVAL, _log_progress, _pct

logger = logging.getLogger(__name__)


# ── ArchiveWorker：归档线程 ──


class ArchiveWorker(QThread):
    """后台归档线程：移动文件到标准库目录，含磁盘检查+断点续做。"""

    progress = pyqtSignal(int)
    batch_ready = pyqtSignal(list)
    finished_signal = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        mgr: Any,
        parsed_list: Any,
        library_root: Any,
        config: Any = None,
        overwrite: bool = False,
        pause_event: Any = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self.parsed_list = parsed_list
        self.library_root = library_root
        self._config = config
        self._overwrite = overwrite
        self._pause_event = pause_event
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        """在线程中执行归档流式处理，批量通知 UI。"""
        try:
            total_size = 0
            for p in self.parsed_list:
                if p.source_path and os.path.exists(p.source_path):
                    total_size += os.path.getsize(p.source_path)
            _disk_root = self.library_root if os.path.exists(self.library_root) else os.path.dirname(self.library_root)
            _, _, free = shutil.disk_usage(_disk_root)
            if total_size > free * 0.9:
                self.error.emit(f"磁盘空间不足: 需要 {total_size / 1024 / 1024:.0f}MB, 剩余 {free / 1024 / 1024:.0f}MB")
                return

            batch: list[tuple[Any, ...]] = []
            last_flush = _time.monotonic()
            _t_start = _time.monotonic()
            _last_log = _t_start

            def on_result(idx: Any, status: Any) -> None:
                """收集归档结果到批次，达到阈值或超时后批量发射。"""
                nonlocal batch, last_flush
                if self._stopped:
                    return
                batch.append((idx, status))
                now = _time.monotonic()
                if len(batch) >= _WORKER_BATCH_SIZE or (batch and now - last_flush >= _WORKER_FLUSH_INTERVAL):
                    if not self._stopped:
                        self.batch_ready.emit(batch)
                    batch = []
                    last_flush = now

            def on_progress(cur: int, total: int) -> None:
                """更新进度百分比，每 15 秒输出阶段日志。"""
                nonlocal _last_log
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                self.progress.emit(_pct(cur, total))
                now = _time.monotonic()
                if now - _last_log >= 15:
                    _log_progress(logger, "归档", cur, total, _t_start)
                    _last_log = now

            self._mgr.archive_standards(
                self.parsed_list, progress_callback=on_progress, on_result=on_result, overwrite=self._overwrite
            )
            if batch and not self._stopped:
                self.batch_ready.emit(batch)
            self.finished_signal.emit()
        except Exception as e:
            self.error.emit(str(e))

    # ── 目标路径计算（静态方法）──

    @staticmethod
    def target_path(parsed: Any, library_root: str, config: Any = None) -> str | None:
        """根据解析信息计算标准文件的目标归档路径。"""
        name = make_standard_filename(
            logical_code=parsed.logical_code,
            number=parsed.number,
            year=parsed.year,
            std_name=parsed.std_name,
            part=getattr(parsed, "part", None),
            language=getattr(parsed, "language", ""),
            num_prefix=getattr(parsed, "num_prefix", ""),
            num_suffix=getattr(parsed, "num_suffix", ""),
            ext=getattr(parsed, "ext", "pdf"),
            raw_number=getattr(parsed, "raw_number", None),
        )
        folder = get_folder_name(parsed.logical_code)
        target_dir = os.path.join(library_root, folder)
        if parsed.effect_status in ("废止", "已废止", "作废", "被代替", "过期"):
            target_dir = os.path.join(target_dir, "过期作废")
        return os.path.join(target_dir, name)

    # ── 实例方法版本 ──

    def _target_path(self, parsed: Any) -> str | None:
        """委托静态方法，使用当前实例的 library_root 和 config。"""
        return ArchiveWorker.target_path(parsed, self.library_root, self._config)
