# pilotstd/ui/workers.py
# 后台 Worker 线程类 — 从 main_window.py 提取
# LogHandler / QueryWorker / DownloadWorker / NormalizeWorker / ArchiveWorker / ScanWorker / AnnounceWorker

import logging
import os
import shutil
import time as _time
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QTextEdit

from ..core.file_utils import make_standard_filename
from ..models import ParsedStdInfo
from ..organizer.industry_lookup import get_folder_name

logger = logging.getLogger(__name__)


def _pct(cur: int, total: int) -> int:
    """cur/total → 0-100 百分比。零除返回0。所有Worker共用。"""
    return int(cur / total * 100) if total > 0 else 0


def _should_log_progress(last_log: float, interval: float = 15.0) -> bool:
    """距上次日志输出已超过 interval 秒时返回 True。"""
    return _time.monotonic() - last_log >= interval


# Worker 批量处理常量
_WORKER_BATCH_SIZE = 50  # 标准 Worker 每批通知条数
_WORKER_FLUSH_INTERVAL = 0.5  # 批量刷新间隔（秒）
_ANNOUNCEMENT_BATCH_SIZE = 20  # 公告处理每批条数


def _log_progress(logger: Any, label: str, current: int, total: int, t_start: float) -> None:
    """输出阶段性进度日志（供各 Worker 在循环中调用）。"""
    elapsed = _time.monotonic() - t_start
    pct = int(current / total * 100) if total > 0 else 0
    logger.info("%s: %d/%d (%d%%) 已耗时 %.0f秒", label, current, total, pct, elapsed)


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
    """将 logging 输出重定向到 QTextEdit，跨线程安全，批量写入防信号洪峰。
    QTextEdit 展示 DEBUG 及以上级别，与文件日志一致。"""

    _log_signal = pyqtSignal(str)

    def __init__(self, widget: QTextEdit) -> None:
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.widget = widget
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S"))
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
            from PyQt6.QtCore import QThread

            app = QApplication.instance()
            if app is not None and QThread.currentThread() == app.thread():
                self._append_text(msg)
            else:
                self._log_signal.emit(msg)
        except RuntimeError:
            pass

    def flush(self) -> None:
        """覆盖 Handler.flush()，防止 atexit 时 C++ 对象已销毁。"""
        try:
            self._flush()
        except RuntimeError:
            pass


class QueryWorker(QThread):
    """后台查询线程 — 调用业务门面的批量查询方法。"""

    progress = pyqtSignal(int)
    result_ready = pyqtSignal(int, object)
    batch_ready = pyqtSignal(list[Any])
    finished_signal = pyqtSignal(list[Any])
    error = pyqtSignal(str)

    def __init__(
        self,
        manager: Any,
        parsed_list: Any,
        pause_event: Any = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._mgr = manager  # StandardManager 实例
        self.parsed_list = parsed_list
        self._pause_event = pause_event
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        try:
            _t_start = _time.monotonic()
            _last_log = _t_start
            # 实时结果回调：每条查询就绪时积累并批量发送到 UI
            _result_batch: list[Any] = []
            _last_flush = _t_start
            _sent_indices: set[int] = set()

            def on_result(idx: int, result: Any) -> None:
                nonlocal _result_batch, _last_flush, _sent_indices
                if self._stopped:
                    return
                _result_batch.append((idx, result))
                _sent_indices.add(idx)
                now = _time.monotonic()
                if len(_result_batch) >= _WORKER_BATCH_SIZE or now - _last_flush >= _WORKER_FLUSH_INTERVAL:
                    if not self._stopped:
                        self.batch_ready.emit(_result_batch)
                    _result_batch = []
                    _last_flush = now

            # 进度回调：每处理一条标准时触发，内联暂停/停止检查
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

            results, _stats = self._mgr.query(
                self.parsed_list,
                progress_callback=on_progress,
                result_callback=on_result,
            )
        except Exception as e:
            self.error.emit(str(e))
            results = []

        # 发送最后一批残留结果（跳过已实时发送的）
        if not self._stopped:
            remaining = [(i, r) for i, r in enumerate(results) if r is not None and i not in _sent_indices]
            if _result_batch:
                self.batch_ready.emit(_result_batch)
            if remaining:
                self.batch_ready.emit(remaining)
        self.finished_signal.emit(results)


class DownloadWorker(QThread):
    """后台下载线程，批量通知 UI 以减少更新频率。"""

    progress = pyqtSignal(int)
    batch_ready = pyqtSignal(list[Any])
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
        import time as _time

        try:
            batch: list[tuple[Any, ...]] = []
            last_flush = _time.monotonic()

            def on_result(idx: Any, status: Any) -> None:
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


class NormalizeWorker(QThread):
    """后台规范化线程：计算规范文件名，批量通知 UI。"""

    progress = pyqtSignal(int)
    batch_ready = pyqtSignal(list[Any])
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
        try:

            def on_batch(batch_rows: Any) -> None:
                if not self._stopped:
                    self.batch_ready.emit(batch_rows)

            def on_progress(cur: Any, total: Any) -> None:
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                self.progress.emit(_pct(cur, total))

            self._mgr.normalize_files_stream(self.parsed_list, on_progress=on_progress, on_batch=on_batch)
            self.finished_signal.emit()
        except Exception as e:
            self.error.emit(str(e))


class ArchiveWorker(QThread):
    """后台归档线程：移动文件到标准库目录，含磁盘检查+断点续做。"""

    progress = pyqtSignal(int)
    batch_ready = pyqtSignal(list[Any])
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
        import time as _time

        try:
            # 磁盘检查（保留——UI 特有需求，避免大批量移动中磁盘满）
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

            self._mgr.organize_stream(self.parsed_list, on_progress=on_progress, on_result=on_result)
            if batch and not self._stopped:
                self.batch_ready.emit(batch)
            self.finished_signal.emit()
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def target_path(parsed: Any, library_root: str, config: Any = None) -> str | None:
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
        )
        folder = get_folder_name(parsed.logical_code)
        target_dir = os.path.join(library_root, folder)
        if parsed.effect_status in ("废止", "已废止", "作废", "被代替"):
            target_dir = os.path.join(target_dir, "过期作废")
        return os.path.join(target_dir, name)

    def _target_path(self, parsed: Any) -> str | None:
        return ArchiveWorker.target_path(parsed, self.library_root, self._config)


class ScanWorker(QThread):
    """后台扫描线程：文件遍历+解析在后台执行，主线程只更新 UI。"""

    progress = pyqtSignal(int, int)
    batch_ready = pyqtSignal(list[Any])
    finished_signal = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, mgr: Any, root_path: str, pause_event: Any = None, parent: Any = None) -> None:
        super().__init__(parent)
        self._mgr = mgr  # StandardManager，不再独立持有 scanner/parser
        self._root_path = root_path
        self._pause_event = pause_event
        self._stopped = False
        self.unrecognized: list[str] = []

    def stop(self) -> None:
        self._stopped = True

    def run(self) -> None:
        import time as _time

        try:
            _t_start = _time.monotonic()
            _last_log = _t_start

            def on_batch(batch_rows: Any) -> None:
                if not self._stopped:
                    self.batch_ready.emit(batch_rows)

            def on_progress(cur: int, total: int) -> None:
                nonlocal _last_log
                if self._stopped:
                    return
                if self._pause_event is not None:
                    self._pause_event.wait()
                self.progress.emit(cur, total)
                now = _time.monotonic()
                if now - _last_log >= 15:
                    _log_progress(logger, "扫描", cur, total, _t_start)
                    _last_log = now

            parsed = self._mgr.scan_directory_stream(self._root_path, on_progress=on_progress, on_batch=on_batch)
            # 收集未识别文件（扫描结果中未被解析的）
            self.unrecognized = []  # scan_directory_stream 内部处理，异常由 facade 记录
            parsed_count = len(parsed)
            self.finished_signal.emit(parsed_count, 0)
        except Exception as e:
            self.error.emit(str(e))


class AnnounceWorker(QThread):
    """后台公告检查线程：分批抓取公告、解析标准、比对缓存、保存附件。"""

    progress = pyqtSignal(int, int, int)
    finished_signal = pyqtSignal()

    def __init__(
        self,
        mgr: Any,
        since_date: Any = None,
        pause_event: Any = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._mgr = mgr  # StandardManager，统一后端
        self._since_date = since_date  # UI传入的起始日期，覆盖fetch_log记录
        self._stopped = False
        self._error = ""
        self._failures: list[dict[str, Any]] = []  # 累积所有适配器失败记录
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
        finally:
            self.finished_signal.emit()


class AutoWorker(QThread):
    """统一自动管线 Worker — 包装 StandardManager.auto_run_stream()。
    在线程中串行执行 scan→query→download→archive，通过 Qt 信号通知 UI。
    取代原有 5 个独立 Worker 的手动拼接。"""

    scan_batch = pyqtSignal(list[Any])  # [(seq, ParsedStdInfo), ...]
    scan_progress = pyqtSignal(int, int)  # (current, total)
    query_progress = pyqtSignal(int, int)  # (current, total)
    query_result = pyqtSignal(int, object)  # (index, QueryResult)
    download_progress = pyqtSignal(int, int)  # (current, total)
    download_result = pyqtSignal(int, str)  # (index, status)
    archive_result = pyqtSignal(int, str)  # (index, status)
    stage_changed = pyqtSignal(str, int, int)  # (stage, current, total)
    finished_signal = pyqtSignal(dict[str, Any])  # report dict
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
        """扫描批量回调 → Qt 信号。AutoWorker 不操作 _parsed_results。"""
        if not self._stopped:
            self.scan_batch.emit(batch_rows)
