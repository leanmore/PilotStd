# pilotstd/ui/workers/download.py — DownloadWorker，从 workers.py 拆分

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ._common import _WORKER_BATCH_SIZE, _WORKER_FLUSH_INTERVAL, _pct


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
        """在线程中执行流式下载，批量发射结果到 UI。"""
        import time as _time

        try:
            batch: list[tuple[Any, ...]] = []
            last_flush = _time.monotonic()

            def on_result(idx: Any, status: Any) -> None:
                """收集下载结果到批次，达到阈值或超时后批量发射。"""
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

            def on_progress(cur: Any, total: Any) -> None:
                """更新下载进度百分比。"""
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                self.progress.emit(_pct(cur, total))

            self._mgr.download_stream(on_progress=on_progress, on_result=on_result)
            if batch and not self._stopped:
                self.batch_ready.emit(batch)
            self.finished_signal.emit()
        except Exception as e:
            self.error.emit(str(e))
