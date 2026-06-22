# pilotstd/ui/controllers/auto_run_mixin.py
# 一键自动运行 + 完成后汇总 — 使用统一 AutoWorker 包装核心层 auto_run_stream

import csv
import logging
import time
from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ...i18n import _
from ..workers import AutoWorker, _pct

logger = logging.getLogger(__name__)


class _ThrottledProgress:
    """节流进度发射器：确保 progress_changed 信号最多每 500ms 发射一次，
    避免 Qt 事件循环合并高频信号导致进度条跳变。"""

    def __init__(self, signal: Any, min_interval: float = 0.5) -> None:
        self._signal = signal
        self._min_interval = min_interval
        self._last_emit = 0.0
        self._last_value = -1

    def emit(self, value: int) -> None:
        now = time.monotonic()
        self._last_value = value
        if now - self._last_emit >= self._min_interval or value >= 100:
            self._signal.emit(value)
            self._last_emit = now

    def flush(self) -> None:
        """强制发射最后一次值（阶段切换时调用，确保最终进度显示）。"""
        if self._last_value >= 0:
            self._signal.emit(self._last_value)
            self._last_emit = time.monotonic()


class AutoRunMixin:
    """一键自动运行 + 完成后汇总弹窗。使用 AutoWorker 统一包装核心层
    StandardManager.auto_run_stream()，替代原有的 5 个独立 Worker 拼接。
    """

    # ── 一键处理 ─────────────────────────────────────────

    def _on_auto_run(self) -> None:
        """自动运行：使用统一 AutoWorker（包装核心层 auto_run_stream）。"""
        if not self._mgr_ready:
            return
        path = self._get_selected_path()
        if not path:
            QMessageBox.information(None,_("title_hint"), _("import_hint"))
            return
        self._start_auto_pipeline(path)

    # ── AutoWorker 连接 ──────────────────────────────────

    def _start_auto_pipeline(self, source_dir: str) -> None:
        """启动统一自动管线（AutoWorker）。连接信号到已有 UI slot。"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._suppress_dialogs = True
        self._clear_table()
        self._parsed_results.clear()
        self._archive_results: list[Any] = []

        # 节流进度发射器（最多每 500ms 发射一次，避免 Qt 合并信号导致跳变）
        self._throttled_progress = _ThrottledProgress(self.progress_changed)
        tp = self._throttled_progress

        self._auto_worker = AutoWorker(self._mgr, source_dir, parent=self)
        self._auto_worker.scan_batch.connect(self._on_scan_batch_ready)
        self._auto_worker.scan_progress.connect(
            lambda cur, total: tp.emit(_pct(cur, total))
        )
        self._auto_worker.query_result.connect(
            lambda idx, result: self._on_query_result_ready(idx, result)
        )
        self._auto_worker.query_progress.connect(
            lambda cur, total: tp.emit(_pct(cur, total))
        )
        self._auto_worker.download_result.connect(self._on_download_batch_ready_single)
        self._auto_worker.download_progress.connect(
            lambda cur, total: tp.emit(_pct(cur, total))
        )
        self._auto_worker.archive_result.connect(self._on_archive_batch_ready_single)
        self._auto_worker.stage_changed.connect(self._on_auto_stage_changed)
        self._auto_worker.error.connect(
            lambda msg: self.status_changed.emit(f"自动运行失败: {msg}")
        )
        self._auto_worker.finished_signal.connect(self._on_auto_pipeline_finished)
        self._auto_worker.start()

    def _on_download_batch_ready_single(self, idx: int, status: str) -> None:
        """AutoWorker 单条下载结果 → 批量 slot 适配。"""
        self._on_download_batch_ready([(idx, status)])

    def _on_archive_batch_ready_single(self, idx: int, status: str) -> None:
        """AutoWorker 单条归档结果 → 批量 slot 适配。"""
        self._on_archive_batch_ready([(idx, status)])

    def _on_auto_stage_changed(self, stage: str, current: int, total: int) -> None:
        """AutoWorker 阶段切换 → 更新按钮状态和进度条。"""
        stage_labels = {
            "scan": "扫描中...",
            "query": "查询中...",
            "download": "下载中...",
            "archive": "归档中...",
            "done": "自动运行完成",
        }
        self.status_changed.emit(stage_labels.get(stage, stage))
        # 阶段切换时 flush 最后一次进度值，确保进度条不被跳过
        tp = getattr(self, "_throttled_progress", None)
        if tp:
            tp.flush()
        if stage != "done":
            self.btn_query.setEnabled(False)
            self.btn_download.setEnabled(False)
            self.btn_cancel.setEnabled(True)
        else:
            self.btn_cancel.setEnabled(False)

    def _on_auto_pipeline_finished(self, report: dict[str, Any]) -> None:
        """AutoWorker 完成 → 恢复 UI + 弹汇总。"""
        self._suppress_dialogs = False
        self.btn_query.setEnabled(True)
        self.btn_download.setEnabled(True)
        self._project.mark_dirty()
        self._show_auto_run_summary()

    # ── 汇总弹窗 ─────────────────────────────────────────

    def _show_auto_run_summary(self) -> None:
        """自动运行完成后弹出汇总统计。"""
        results = self._parsed_results
        if not results:
            return

        total = len(results)
        not_found = [p for p in results if not p.std_name]
        expired = [p for p in results if p.effect_status in ("废止", "已废止", "作废")]
        adopted = [p for p in results if p.is_adopted]

        manual_all = []
        for p in not_found:
            label = f"{p.get_full_number()}  {_('auto_run_manual_row_not_found')}"
            manual_all.append(label)
        for p in adopted:
            label = f"{p.get_full_number()}  {_('auto_run_manual_row_adopted')}"
            manual_all.append(label)

        msg = (
            _("auto_run_summary_total").format(total=total)
            + "\n\n"
            + _("auto_run_summary_found").format(count=total - len(not_found))
            + "\n"
            + _("auto_run_summary_not_found").format(count=len(not_found))
            + "\n"
            + _("auto_run_summary_expired").format(count=len(expired))
            + "\n"
            + _("auto_run_summary_adopted").format(count=len(adopted))
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(_("auto_run_summary_title"))
        dlg.resize(550, 380)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel(msg))

        if manual_all:
            layout.addWidget(QLabel(_("auto_run_manual_label")))
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(manual_all))
            text.setMaximumHeight(150)
            layout.addWidget(text)

        btn_layout = QHBoxLayout()
        btn_txt = QPushButton(_("btn_export_txt"))
        btn_csv = QPushButton(_("btn_export_csv"))
        btn_close = QPushButton(_("btn_close"))
        btn_layout.addWidget(btn_txt)
        btn_layout.addWidget(btn_csv)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        def _export(fmt: str) -> None:
            filter_str = _("file_filter_csv") if fmt == "csv" else _("file_filter_txt")
            path, __ = QFileDialog.getSaveFileName(
                None, _("dialog_export_summary"), f"auto_run_summary.{fmt}", filter_str
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8-sig") as f:
                    if fmt == "csv":
                        w = csv.writer(f)
                        w.writerow(
                            [
                                _("csv_header_std_number"),
                                _("csv_header_std_name"),
                                _("csv_header_reason"),
                            ]
                        )
                        for item in manual_all:
                            parts = item.split("  ")
                            w.writerow(parts if len(parts) >= 2 else [item, "", ""])
                    else:
                        f.write(_("auto_run_manual_txt_header"))
                        f.write("\n".join(manual_all))
                self.status_changed.emit(f"已导出: {path}")
            except OSError as e:
                logger.error(f"导出汇总失败: {e}")

        btn_txt.clicked.connect(lambda: _export("txt"))
        btn_csv.clicked.connect(lambda: _export("csv"))
        btn_close.clicked.connect(dlg.accept)
        dlg.exec()
