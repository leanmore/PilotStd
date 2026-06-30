# pilotstd/ui/workers/announce.py — AnnounceWorker，从 workers.py 拆分

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal


class AnnounceWorker(QThread):
    """后台公告检查线程：分批抓取公告、解析标准、比对缓存、保存附件。"""

    progress = pyqtSignal(int, int, int)
    finished_signal = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mgr: Any, since_date: Any = None, pause_event: Any = None, parent: Any = None) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self._since_date = since_date
        self._stopped = False
        self._error = ""
        self._failures: list[dict[str, Any]] = []
        self._total = 0
        self._matched = 0
        self._pause_event = pause_event

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        try:

            def on_progress(cur: int, total: int, matched: int) -> None:
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                self._matched = matched
                self._total = total
                self.progress.emit(cur, total, matched)

            def on_adapter_done(std_type: Any, result: Any) -> None:
                if result is None:
                    self._failures.append({"type": std_type, "error": "无响应"})
                elif "error" in result:
                    self._error = result["error"]
                    self._failures.append({"type": std_type, "error": result["error"]})

            self._mgr.announce_stream(
                since_date=self._since_date or "",
                on_progress=on_progress,
                on_adapter_done=on_adapter_done,
            )
        except Exception as e:
            self._error = str(e)
            self.error.emit(str(e))
        finally:
            self.finished_signal.emit()
