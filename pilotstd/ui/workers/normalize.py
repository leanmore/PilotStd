# pilotstd/ui/workers/normalize.py — NormalizeWorker，从 workers.py 拆分

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ._common import _pct


class NormalizeWorker(QThread):
    """后台规范化线程：计算规范文件名，批量通知 UI。"""

    progress = pyqtSignal(int)
    batch_ready = pyqtSignal(list)
    finished_signal = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mgr: Any, parsed_list: Any, pause_event: Any = None, parent: Any = None) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self.parsed_list = parsed_list
        self._stopped = False
        self._pause_event = pause_event

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        """在线程中执行流式规范化，批量发射结果。
        try/finally 保证任何退出路径都恰好发射一次 finished_signal。
        """
        try:

            def on_batch(batch_rows: Any) -> None:
                """发射批次结果到 UI（非停止状态）。"""
                if not self._stopped:
                    self.batch_ready.emit(batch_rows)

            def on_progress(cur: Any, total: Any) -> None:
                """更新规范化进度百分比。"""
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                self.progress.emit(_pct(cur, total))

            self._mgr.normalize_files_stream(self.parsed_list, on_progress=on_progress, on_batch=on_batch)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished_signal.emit()
