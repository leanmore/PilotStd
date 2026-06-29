# pilotstd/ui/workers/auto.py — AutoWorker，从 workers.py 拆分

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal


class AutoWorker(QThread):
    """统一自动管线 Worker — 包装 StandardManager.auto_run_stream()。
    在线程中串行执行 scan→query→download→archive，通过 Qt 信号通知 UI。
    """

    scan_batch = pyqtSignal(list)
    scan_progress = pyqtSignal(int, int)
    query_progress = pyqtSignal(int, int)
    query_result = pyqtSignal(int, object)
    download_progress = pyqtSignal(int, int)
    download_result = pyqtSignal(int, str)
    archive_result = pyqtSignal(int, str)
    stage_changed = pyqtSignal(str, int, int)
    finished_signal = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, mgr: Any, root_path: str, parent: Any = None) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self._root_path = root_path
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        try:
            report = self._mgr.auto_run_stream(
                self._root_path,
                on_scan_batch=self._emit_scan_batch,
                on_scan_progress=lambda c, t: self.scan_progress.emit(c, t),
                on_query_progress=lambda c, t: self.query_progress.emit(c, t),
                on_query_result=lambda i, r: self.query_result.emit(i, r),
                on_download_progress=lambda c, t: self.download_progress.emit(c, t),
                on_download_result=lambda i, s: self.download_result.emit(i, s),
                on_archive_result=lambda i, s: self.archive_result.emit(i, s),
                on_stage_change=lambda s, c, t: self.stage_changed.emit(s, c, t),
            )
        except Exception as e:
            self.error.emit(str(e))
            return
        self.finished_signal.emit(report)

    def _emit_scan_batch(self, batch_rows: list[Any]) -> None:
        if not self._stopped:
            self.scan_batch.emit(batch_rows)
