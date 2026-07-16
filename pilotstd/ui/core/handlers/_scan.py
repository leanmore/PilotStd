# pilotstd/ui/core/handlers/_scan.py
"""ScanUIHandler — 扫描 UI 状态管理，替代 ScanMixin。"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox, QTableWidget

if TYPE_CHECKING:
    from ....core.config import ConfigManager

from ....i18n import _
from ...workers import RowUpdate, ScanWorker
from ..event_bus import EventBus
from .scan_flow_engine import ScanFlowEngine

logger = logging.getLogger(__name__)


class ScanUIHandler:
    """扫描 UI 状态管理。

    职责：扫描前置检查、调用 mgr.scan_stream、表格更新、进度动画、结果弹窗。
    """

    def __init__(
        self,
        mgr: Any,
        config: ConfigManager,
        pause_event: Any,
        parent_widget: Any,
        work_table: QTableWidget,
        parsed_results: list[Any],
        unrecognized_files: list[str],
        scan_source_root: str,
        status_callback: Callable[[str], None],
        suppress_dialogs: Callable[[], bool],
        add_table_row: Callable[..., None],
        register_task: Callable[..., None],
        project_mark_dirty: Callable[[], None],
        clear_table: Callable[[], None],
        update_button_states: Callable[[], None],
        question_dlg: Callable[..., Any],
    ) -> None:
        self._mgr = mgr
        self._config = config
        self._pause_event = pause_event
        self._parent = parent_widget
        self._work_table = work_table
        self._parsed_results = parsed_results
        self._unrecognized_files = unrecognized_files
        self._scan_source_root = scan_source_root
        self._status_cb = status_callback
        self._suppress_dialogs = suppress_dialogs
        self._add_table_row = add_table_row
        self._register_task = register_task
        self._project_mark_dirty = project_mark_dirty
        self._clear_table = clear_table
        self._update_button_states = update_button_states
        self._question_dlg = question_dlg
        self._scan_worker: ScanWorker | None = None
        self._engine = ScanFlowEngine()

        # 进度动画控制（Handler 内部管理）
        self._target_progress = 0
        self._current_progress = 0.0
        self._progress_timer = QTimer()
        self._progress_timer.setInterval(50)
        self._progress_timer.timeout.connect(self._animate_progress)

    # ── 公开方法 ─────────────────────────────────────────────

    def run_scan(self, root_path: str) -> None:
        """执行文件扫描并填充工作区表格。"""
        if not root_path or not os.path.exists(root_path):
            self._status_cb(_("status_select_valid_path"))
            return

        # 工作区非空 → 追加/覆盖保护
        if self._parsed_results and not self._suppress_dialogs():
            msg = _("scan_overwrite_warning").format(count=len(self._parsed_results))
            reply = self._question_dlg(_("scan_overwrite_title"), msg)
            if reply == QMessageBox.StandardButton.No:
                pass  # 追加
            else:
                self._clear_table()
                self._parsed_results.clear()
        else:
            self._clear_table()
            self._parsed_results.clear()
        QApplication.processEvents()

        if os.path.isfile(root_path):
            self._scan_single_file(root_path)
        else:
            self._scan_directory(root_path)
        self._project_mark_dirty()

    def stop_workers(self) -> None:
        """停止正在运行的扫描 Worker。"""
        w = self._scan_worker
        if w is not None and w.isRunning():
            w.stop()
            w.quit()
            if not w.wait(5000):
                w.terminate()
                w.wait()

    # ── 进度管理 ─────────────────────────────────────────────

    def on_raw_progress(self, current: int, total: int) -> None:
        """原始进度更新（来自 Worker 信号）。"""
        self._target_progress = int(current / max(total, 1) * 100)
        if not self._progress_timer.isActive():
            self._progress_timer.start()

    def reset_progress_bar(self) -> None:
        """重置进度状态。"""
        self._target_progress = 0
        self._current_progress = 0.0
        self._progress_timer.stop()

    def force_finish_progress(self) -> None:
        """强制完成进度。"""
        self._target_progress = 100
        self._current_progress = 100.0
        self._progress_timer.stop()

    def _animate_progress(self) -> None:
        """进度动画：平滑逼近目标值。"""
        diff = self._target_progress - self._current_progress
        if abs(diff) < 0.5:
            self._current_progress = float(self._target_progress)
            self._progress_timer.stop()
        else:
            self._current_progress += diff * 0.3

    # ── 内部方法 ─────────────────────────────────────────────

    def _scan_single_file(self, file_path: str) -> None:
        """直接解析单个文件，优先从索引恢复，其次 Engine 解析，最后回退 mgr 解析。"""
        from ....core.file_utils import hash_file_content

        filename = os.path.basename(file_path)
        self._status_cb(f"扫描文件: {filename}")
        self._scan_source_root = os.path.dirname(os.path.abspath(file_path))
        self._unrecognized_files.clear()

        parsed = None
        file_hash = ""
        if self._mgr.file_index:
            file_hash = hash_file_content(file_path)
            existing = self._mgr.get_file_index(file_path)
            if existing and existing["file_hash"] == file_hash and file_hash:
                parsed = self._mgr.restore_parsed_from_index(file_path)

        if parsed is None:
            # 尝试 Engine 文件名解析 → PDF 头解析 → mgr 回退
            std_info = self._engine.parse_filename_to_std(filename)
            if std_info is None and filename.lower().endswith(".pdf"):
                try:
                    with open(file_path, "rb") as f:
                        header = f.read(1024)
                    std_info = self._engine.parse_pdf_header(header)
                except OSError:
                    std_info = None
            if std_info is None:
                parsed = self._mgr.parse_standard_number(filename)
            # 当 Engine 解析成功时，仍用 mgr 获取完整 ParsedStdInfo 对象
            if std_info is not None and parsed is None:
                parsed = self._mgr.parse_standard_number(filename)

        if parsed:
            parsed.source_path = file_path
            self._parsed_results.append(parsed)
            self._add_table_row(
                RowUpdate(
                    seq=self._work_table.rowCount() + 1,
                    parsed=parsed,
                    work_status="已扫描",
                    total=len(self._parsed_results),
                )
            )
            self._status_cb(_("status_scan_single_ok"))
            self._register_task("扫描", 1, 1, 0)
            self._mgr.upsert_file_index(
                file_path,
                parsed.logical_code,
                parsed.number,
                parsed.year,
                part=parsed.part,
                std_name=parsed.std_name,
                status="现行",
            )
        else:
            self._status_cb(f"无法识别标准号: {filename}")
            self._unrecognized_files.append(file_path)

    def _scan_directory(self, dir_path: str) -> None:
        """后台线程扫描目录。"""
        self._status_cb(f"扫描中: {dir_path}")
        self._scan_source_root = os.path.abspath(dir_path)
        self._unrecognized_files.clear()
        self.reset_progress_bar()

        self._scan_worker = ScanWorker(self._mgr, dir_path, pause_event=self._pause_event, parent=self._parent)
        from PyQt6.QtCore import Qt

        self._scan_worker.batch_ready.connect(self.on_scan_batch_ready, Qt.ConnectionType.QueuedConnection)
        self._scan_worker.batch_ready.connect(
            lambda data: self._publish_event("scan.batch_ready", {"rows": data}),
            Qt.ConnectionType.QueuedConnection,
        )
        self._scan_worker.progress.connect(self.on_raw_progress, Qt.ConnectionType.QueuedConnection)
        self._scan_worker.finished_signal.connect(self.on_scan_finished, Qt.ConnectionType.QueuedConnection)
        self._scan_worker.finished_signal.connect(
            lambda s, f: self._publish_event("scan.finished", {"success": s, "failed": f}),
            Qt.ConnectionType.QueuedConnection,
        )
        self._scan_worker.error.connect(
            lambda msg: self._status_cb(f"扫描失败: {msg}"), Qt.ConnectionType.QueuedConnection
        )
        self._scan_worker.error.connect(
            lambda msg: self._publish_event("scan.error", {"error": msg}),
            Qt.ConnectionType.QueuedConnection,
        )
        self._scan_worker.start()

    def on_scan_batch_ready(self, batch_rows: list[Any]) -> None:
        """后台线程批量通知：追加已解析文件到表格。"""
        self._work_table.setUpdatesEnabled(False)
        try:
            for seq, parsed in batch_rows:
                self._parsed_results.append(parsed)
                self._add_table_row(
                    RowUpdate(
                        seq=seq,
                        parsed=parsed,
                        work_status="已扫描",
                        total=0,
                    )
                )
        finally:
            self._work_table.setUpdatesEnabled(True)

    def on_scan_finished(self, success: int, failed: int) -> None:
        """扫描完成：汇总统计并弹窗。"""
        self.force_finish_progress()
        self._unrecognized_files.clear()
        if self._scan_worker:
            self._unrecognized_files.extend(self._scan_worker.unrecognized)
        total = success + failed
        self._status_cb(f"扫描完成: {total} 个文件, {success} 个识别成功, {failed} 个无法识别")
        self._register_task("扫描", total, success, failed)
        self._project_mark_dirty()

        if failed > 0 and not self._suppress_dialogs():
            QMessageBox.information(
                self._parent,
                _("dialog_scan_result"),
                _("msg_scan_complete").format(success=success, failed=failed) + "\n\n" + _("msg_scan_hint"),
            )
        self._update_button_states()

    # ── 事件发布 ─────────────────────────────────────────────

    @staticmethod
    def _publish_event(event_name: str, data: Any) -> None:
        """封装事件发布，便于统一加日志/监控。"""
        EventBus.instance().publish(event_name, data)
