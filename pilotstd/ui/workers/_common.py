# pilotstd/ui/workers/_common.py
# 共享工具函数、常量、数据类 — 从 workers.py 拆分

import logging
import time as _time
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QTextEdit

from pilotstd.core.logger import _TagFormatter

from ...models import ParsedStdInfo

logger = logging.getLogger(__name__)

# Worker 批量处理常量
_WORKER_BATCH_SIZE = 50
_WORKER_FLUSH_INTERVAL = 0.5
_ANNOUNCEMENT_BATCH_SIZE = 20


def _pct(cur: int, total: int) -> int:
    """cur/total → 0-100 百分比。零除返回0。所有Worker共用。"""
    return int(cur / total * 100) if total > 0 else 0


def _should_log_progress(last_log: float, interval: float = 15.0) -> bool:
    """距上次日志输出已超过 interval 秒时返回 True。"""
    return _time.monotonic() - last_log >= interval


def _log_progress(logr: Any, label: str, current: int, total: int, t_start: float) -> None:
    """输出阶段性进度日志（供各 Worker 在循环中调用）。"""
    elapsed = _time.monotonic() - t_start
    pct_val = int(current / total * 100) if total > 0 else 0
    logr.info("%s: %d/%d (%d%%) 已耗时 %.0f秒", label, current, total, pct_val, elapsed)


@dataclass
class RowUpdate:
    """工作表格行更新数据，替代 _add_table_row 的十参数签名。"""

    seq: int
    parsed: ParsedStdInfo
    work_status: str = ""
    effect_status: str = ""
    implement_date: str = ""
    std_name_override: str = ""
    responsible_dept: str = ""
    publish_date: str = ""
    is_adopted: bool = False
    total: int = 0


class LogHandler(logging.Handler, QObject):
    """将 logging 输出重定向到 QTextEdit，跨线程安全，批量写入防信号洪峰。"""

    _log_signal = pyqtSignal(str)

    def __init__(self, widget: QTextEdit) -> None:
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.widget = widget
        self.setFormatter(_TagFormatter())
        self._log_signal.connect(self._append_text, Qt.ConnectionType.QueuedConnection)
        self.setLevel(logging.DEBUG)
        self._buf: list[str] = []
        self._buf_timer = QTimer()
        self._buf_timer.setSingleShot(True)
        self._buf_timer.setInterval(200)
        self._buf_timer.timeout.connect(self._flush)

    def _flush(self) -> None:
        if not self._buf:
            return
        try:
            w = self.widget
            if w is None:
                self._buf.clear()
                return
            w.append("\n".join(self._buf))
            sb = w.verticalScrollBar()
            if sb is not None:
                sb.setValue(sb.maximum())
        except RuntimeError:
            pass
        self._buf.clear()

    def _append_text(self, msg: str) -> None:
        self._buf.append(msg)
        if not self._buf_timer.isActive():
            self._buf_timer.start()

    def emit(self, record: Any) -> None:
        try:
            msg = self.format(record)
            from PyQt6.QtCore import QThread as _QThread

            app = QApplication.instance()
            if app is not None and _QThread.currentThread() == app.thread():
                self._append_text(msg)
            else:
                self._log_signal.emit(msg)
        except RuntimeError:
            pass

    def flush(self) -> None:
        try:
            self._flush()
        except RuntimeError:
            pass
