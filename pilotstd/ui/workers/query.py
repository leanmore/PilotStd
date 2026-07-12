# pilotstd/ui/workers/query.py — QueryWorker，从 workers.py 拆分

import logging
import time as _time
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ._common import _WORKER_BATCH_SIZE, _WORKER_FLUSH_INTERVAL, _log_progress, _pct

logger = logging.getLogger(__name__)


class QueryWorker(QThread):
    """后台查询线程 — 调用业务门面的批量查询方法。"""

    progress = pyqtSignal(int)
    result_ready = pyqtSignal(int, object)
    batch_ready = pyqtSignal(list)
    finished_signal = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        manager: Any,
        parsed_list: Any,
        pause_event: Any = None,
        site: str | None = None,
        force_refresh: bool = False,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._mgr = manager
        self.parsed_list = parsed_list
        self._pause_event = pause_event
        self._site = site
        self._force_refresh = force_refresh
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        try:
            _t_start = _time.monotonic()
            _last_log = _t_start
            _result_batch: list[Any] = []
            _last_flush = _t_start
            _sent_indices: set[int] = set()

            def on_result(idx: int, result: Any) -> None:
                nonlocal _result_batch, _last_flush, _sent_indices
                if self._stopped:
                    return
                _result_batch.append((idx, result))
                _sent_indices.add(idx)
                self.result_ready.emit(idx, result)
                now = _time.monotonic()
                if len(_result_batch) >= _WORKER_BATCH_SIZE or now - _last_flush >= _WORKER_FLUSH_INTERVAL:
                    if not self._stopped:
                        self.batch_ready.emit(_result_batch)
                    _result_batch = []
                    _last_flush = now

            def on_progress(current: int, total: int) -> None:
                nonlocal _last_log
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                percent = _pct(current, total)
                self.progress.emit(percent)
                now = _time.monotonic()
                if now - _last_log >= 15:
                    _log_progress(logger, "查询", current, total, _t_start)
                    _last_log = now

            if self._pause_event is not None:
                self._mgr.set_pause_event(self._pause_event)
            results, _stats = self._mgr.query_stream(
                self.parsed_list,
                on_progress=on_progress,
                on_result=on_result,
                site=self._site,
                force_refresh=self._force_refresh,
            )
        except Exception as e:
            self.error.emit(str(e))
            results = []

        if not self._stopped:
            remaining = [(i, r) for i, r in enumerate(results) if r is not None and i not in _sent_indices]
            if _result_batch:
                self.batch_ready.emit(_result_batch)
            if remaining:
                self.batch_ready.emit(remaining)
        self.finished_signal.emit(results)
