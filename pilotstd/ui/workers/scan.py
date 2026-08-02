# pilotstd/ui/workers/scan.py — ScanWorker，从 workers.py 拆分
#
# 后台扫描线程：文件遍历+解析在后台执行，主线程只更新 UI。

import logging
import time as _time
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ._common import _log_progress

logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """后台扫描线程：文件遍历+解析在后台执行，主线程只更新 UI。"""

    progress = pyqtSignal(int, int)
    batch_ready = pyqtSignal(list)
    finished_signal = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, mgr: Any, root_path: str, pause_event: Any = None, parent: Any = None) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self._root_path = root_path
        self._pause_event = pause_event
        self._stopped = False
        self.unrecognized: list[str] = []

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        """在线程中执行流式扫描，节流发射进度信号防止事件队列撑爆。
        try/finally 保证任何退出路径（正常/异常/提前返回）都恰好发射一次 finished_signal。
        """
        parsed_count = 0
        failed_count = 0
        try:
            _t_start = _time.monotonic()
            _last_log = _t_start
            _last_signal = _t_start

            def on_batch(batch_rows: Any) -> None:
                """每批解析结果就绪时的回调，发射 batch_ready 信号。"""
                if not self._stopped:
                    self.batch_ready.emit(batch_rows)

            def on_progress(cur: int, total: int) -> None:
                nonlocal _last_log, _last_signal
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                now = _time.monotonic()
                # 节流：每 50 个文件 / 每 500ms / 最后一批 才发射一次信号，防止事件队列撑爆
                if cur % 50 == 0 or cur == total or now - _last_signal >= 0.5:
                    self.progress.emit(cur, total)
                    _last_signal = now
                if now - _last_log >= 15:
                    _log_progress(logger, "扫描", cur, total, _t_start)
                    _last_log = now

            parsed = self._mgr.scan_stream(self._root_path, on_progress=on_progress, on_batch=on_batch)
            self.unrecognized = []
            parsed_count = len(parsed)
        except Exception as e:
            self.error.emit(str(e))
            failed_count = 1
        finally:
            self.finished_signal.emit(parsed_count, failed_count)
