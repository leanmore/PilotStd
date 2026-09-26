# 项目//工作者/下载脚本—，从工作者脚本拆分

import logging
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ._common import (
    _WORKER_BATCH_SIZE,
    _WORKER_FLUSH_INTERVAL,
    WorkerAborted,
    _pct,
    check_stop,
    wait_pause_or_abort,
)

logger = logging.getLogger(__name__)


class DownloadWorker(QThread):
    """后台下载线程，批量通知 UI 以减少更新频率。"""

    progress = pyqtSignal(int)
    batch_ready = pyqtSignal(list)
    finished_signal = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mgr: Any, parsed_list: Any, pause_event: Any = None, parent: Any = None) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self.parsed_list = parsed_list
        self._pause_event = pause_event
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        """在线程中执行流式下载，批量发射结果到 UI。
        try/finally 保证任何退出路径都恰好发射一次 finished_signal。
        """
        import time as _time

        _t_start = _time.monotonic()
        try:
            batch: list[tuple[Any, ...]] = []
            last_flush = _time.monotonic()

            def on_result(idx: Any, status: Any) -> None:
                """收集下载结果到批次，达到阈值或超时后批量发射。"""
                nonlocal batch, last_flush
                check_stop(self)  # #17a：单条粒度中断检查点（中止底层下载流）
                batch.append((idx, status))
                now = _time.monotonic()
                if len(batch) >= _WORKER_BATCH_SIZE or (batch and now - last_flush >= _WORKER_FLUSH_INTERVAL):
                    self.batch_ready.emit(batch)
                    batch = []
                    last_flush = now

            def on_progress(cur: Any, total: Any) -> None:
                """更新下载进度百分比。"""
                check_stop(self)  # #17a
                wait_pause_or_abort(self._pause_event, self)
                self.progress.emit(_pct(cur, total))

            logger.info("[DownloadWorker] about to call download_stream")
            self._mgr.download_stream(on_progress=on_progress, on_result=on_result)
            logger.info("[DownloadWorker] download_stream returned")
            if batch and not self._stopped and not self.isInterruptionRequested():
                self.batch_ready.emit(batch)
        except WorkerAborted:
            logger.info("[DownloadWorker] 收到停止请求，已在中止点退出")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            _elapsed = _time.monotonic() - _t_start
            logger.info("[DownloadWorker] elapsed=%.1fs", _elapsed)
            # 块保证_在正常/异常/提前返回三条路径都恰好发射一次
            self.finished_signal.emit()
