# 模块：pilotstd/ui/workers/_common.py
# 共享工具函数、常量、数据类 — 从 workers.py 拆分
# 分隔
# 所有 Worker 共用的批量处理常量、进度工具和日志处理器。

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


# ── 进度计算 ──


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


# ── RowUpdate：表格行更新数据类 ──


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


# ── LogHandler：日志 → QTextEdit 重定向 ──


class LogHandler(logging.Handler, QObject):
    """将 logging 输出重定向到 QTextEdit，跨线程安全，批量写入防信号洪峰。"""

    _log_signal = pyqtSignal(str)

    def __init__(self, widget: QTextEdit) -> None:
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.widget = widget
        self._closed = False
        self.setFormatter(_TagFormatter())
        self._log_signal.connect(self._append_text, Qt.ConnectionType.QueuedConnection)
        self.setLevel(logging.DEBUG)
        self._buf: list[str] = []
        self._buf_timer = QTimer()
        self._buf_timer.setSingleShot(True)
        self._buf_timer.setInterval(200)
        self._buf_timer.timeout.connect(self._flush)

    def close(self) -> None:
        """在 Qt 对象销毁前关闭处理器，释放 Qt 引用。

        防御 C++ 对象已被 Qt 析构（atexit 期间先于 logging shutdown 触发），
        避免 RuntimeError 淹没 CI 日志。
        """
        self._closed = True
        try:
            _sip = __import__("PyQt6.sip", fromlist=["isdeleted"])
            if hasattr(_sip, "isdeleted") and _sip.isdeleted(self):
                self.widget = None
                return
        except (AttributeError, ImportError):
            pass
        self.widget = None
        try:
            logging.getLogger().removeHandler(self)
        except Exception:
            pass

    # ── 批量刷新缓冲区 ──

    def _flush(self) -> None:
        """将缓冲区中的日志批量写入 QTextEdit 并滚动到底部。"""
        if self._closed or not self._buf:
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
            self._closed = True
            self.widget = None
        self._buf.clear()

    # ── 追加日志到缓冲区 ──

    def _append_text(self, msg: str) -> None:
        """将单条日志追加到缓冲区，触发批量刷新定时器。"""
        if self._closed:
            return
        self._buf.append(msg)
        if not self._buf_timer.isActive():
            self._buf_timer.start()

    # ── logging.Handler 接口 ──

    def emit(self, record: Any) -> None:
        """logging.Handler 的 emit 接口：格式化日志记录并线程安全地追加。"""
        if self._closed:
            return
        try:
            msg = self.format(record)
            from PyQt6.QtCore import QThread as _QThread

            app = QApplication.instance()
            if app is not None and _QThread.currentThread() == app.thread():
                self._append_text(msg)
            else:
                self._log_signal.emit(msg)
        except RuntimeError:
            self._closed = True
            self.widget = None

    def flush(self) -> None:
        """logging.Handler 的 flush 接口：立即刷新缓冲区。"""
        if self._closed:
            return
        try:
            self._flush()
        except RuntimeError:
            self._closed = True
            self.widget = None


# ── 安全关闭日志 ──


def flush_logs() -> None:
    """在 Qt 销毁前安全关闭 logging，避免 atexit 访问已析构对象。"""
    logging.shutdown()
