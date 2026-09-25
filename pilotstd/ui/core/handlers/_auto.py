# 模块：项目//核心/处理器/_脚本
"""AutoUIHandler — 自动管线 UI 状态管理，替代 AutoRunMixin。"""

from __future__ import annotations

import csv
import logging
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from ....core.config import ConfigManager

from ....i18n import _
from ...qt_lifecycle import stop_worker_gracefully
from ...workers import AutoWorker
from ..event_bus import EventBus
from .auto_flow_engine import AutoFlowEngine

logger = logging.getLogger(__name__)


class AutoUIHandler:
    """自动管线 UI 状态管理，替代 AutoRunMixin。

    职责：启动 auto_run_stream Worker、转发阶段信号、完成回调。
    """

    def __init__(
        self,
        mgr: Any,
        config: ConfigManager,
        pause_event: Any,
        parent_widget: Any,
        work_table: QTableWidget,
        parsed_results: list[Any],
        status_callback: Callable[[str], None],
        progress_callback: Callable[[int], None],
        # 用户界面回调
        clear_table: Callable[[], None],
        force_finish_progress: Callable[[], None],
        reset_progress: Callable[[], None],
        project_mark_dirty: Callable[[], None],
        set_suppress_dialogs: Callable[[bool], None],
        set_query_btn_enabled: Callable[[bool], None],
        set_download_btn_enabled: Callable[[bool], None],
        set_cancel_btn_enabled: Callable[[bool], None],
        set_progress_format: Callable[[str], None],
        set_progress_bar_visible: Callable[[bool], None],
        show_auto_error_style: Callable[[], None],
        # 引用（用于信号路由）
        scan_handler: Any = None,
        query_handler: Any = None,
        download_handler: Any = None,
        archive_handler: Any = None,
    ) -> None:
        self._mgr = mgr
        self._config = config
        self._pause_event = pause_event
        self._parent = parent_widget
        self._work_table = work_table
        self._parsed_results = parsed_results
        self._status_cb = status_callback
        self._progress_cb = progress_callback
        self._clear_table = clear_table
        self._force_finish_progress = force_finish_progress
        self._reset_progress = reset_progress
        self._project_mark_dirty = project_mark_dirty
        self._set_suppress_dialogs = set_suppress_dialogs
        self._set_query_btn_enabled = set_query_btn_enabled
        self._set_download_btn_enabled = set_download_btn_enabled
        self._set_cancel_btn_enabled = set_cancel_btn_enabled
        self._set_progress_format = set_progress_format
        self._set_progress_bar_visible = set_progress_bar_visible
        self._show_auto_error_style = show_auto_error_style
        self._scan_handler = scan_handler
        self._query_handler = query_handler
        self._download_handler = download_handler
        self._archive_handler = archive_handler
        self._auto_worker: AutoWorker | None = None

    # ── 公开方法 ─────────────────────────────────────────────

    def start_auto_pipeline(self, source_dir: str) -> None:
        """启动自动管线 Worker，连接所有信号。"""
        # 初始化用户界面状态：显示进度条，清零，隐藏弹窗，清空表格
        self._set_progress_bar_visible(True)
        self._progress_cb(0)
        self._set_progress_format("%p%")
        self._set_suppress_dialogs(True)
        self._clear_table()
        self._parsed_results.clear()

        # 创建并连接各阶段信号
        self._auto_worker = AutoWorker(self._mgr, source_dir, parent=self._parent)
        # 扫描阶段信号
        self._auto_worker.scan_batch.connect(self._on_scan_batch_ready)
        self._auto_worker.scan_progress.connect(self._on_raw_progress)
        # 查询阶段信号
        self._auto_worker.query_result.connect(self._on_query_result_ready)
        self._auto_worker.query_progress.connect(self._on_raw_progress)
        # 下载阶段信号
        self._auto_worker.download_result.connect(self._on_download_batch_ready_single)
        self._auto_worker.download_progress.connect(self._on_raw_progress)
        # 归档阶段信号
        self._auto_worker.archive_result.connect(self._on_archive_batch_ready_single)
        # 阶段切换和完成信号
        self._auto_worker.stage_changed.connect(self._on_auto_stage_changed)
        self._auto_worker.error.connect(self._on_auto_error)
        self._auto_worker.finished_signal.connect(self._on_auto_pipeline_finished)
        self._auto_worker.start()

    def stop_workers(self) -> None:
        """停止正在运行的自动管线 Worker（先断全部阶段信号再协作式停止，严禁 terminate）。"""
        w = self._auto_worker
        if w is None:
            return
        stop_worker_gracefully(
            w,
            signals=(
                w.scan_batch,
                w.scan_progress,
                w.query_result,
                w.query_progress,
                w.download_result,
                w.download_progress,
                w.archive_result,
                w.stage_changed,
                w.error,
                w.finished_signal,
            ),
        )

    # ── 信号路由（内部） ──────────────────────────────────────

    def _on_scan_batch_ready(self, batch_rows: list[Any]) -> None:
        """转发 scan_batch → ScanUIHandler。"""
        if self._scan_handler is not None:
            self._scan_handler.on_scan_batch_ready(batch_rows)

    def _on_query_result_ready(self, idx: int, result: Any) -> None:
        """转发 query_result → QueryUIHandler。"""
        if self._query_handler is not None:
            self._query_handler.on_query_result_ready(idx, result)

    def _on_download_batch_ready_single(self, idx: int, status: str) -> None:
        """单条下载结果 → 批量 slot 适配转发。"""
        if self._download_handler is not None:
            self._download_handler._on_batch_ready([(idx, status)])

    def _on_archive_batch_ready_single(self, idx: int, status: str) -> None:
        """单条归档结果 → 批量 slot 适配转发。"""
        if self._archive_handler is not None:
            self._archive_handler.on_archive_batch_ready([(idx, status)])

    def _on_raw_progress(self, current: int, total: int) -> None:
        """进度信号适配（current/total → 0-100%）。"""
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_cb(pct)

    # ── 自动管线回调 ─────────────────────────────────────────

    def _on_auto_error(self, msg: str) -> None:
        """AutoWorker 异常 → 进度条变红 + 状态栏错误信息 + 发布事件。"""
        self._show_auto_error_style()
        self._status_cb(f"{_('auto_run_failed')}: {msg}")
        EventBus.instance().publish("auto.pipeline.error", {"error": msg})

    def _on_auto_stage_changed(self, stage: str, current: int, total: int) -> None:
        """阶段切换 → 更新按钮状态和进度条，同步发布事件。"""
        stage_labels = {
            "scan": "扫描中...",
            "query": "查询中...",
            "download": "下载中...",
            "archive": "归档中...",
            "done": "自动运行完成",
        }
        self._status_cb(stage_labels.get(stage, stage))
        self._force_finish_progress()
        self._reset_progress()
        if stage != "done":
            self._set_query_btn_enabled(False)
            self._set_download_btn_enabled(False)
            self._set_cancel_btn_enabled(True)
        else:
            self._set_cancel_btn_enabled(False)
        EventBus.instance().publish(f"auto.stage.{stage}", {"stage": stage, "current": current, "total": total})

    def _on_auto_pipeline_finished(self, report: dict[str, Any]) -> None:
        """AutoWorker 完成 → 恢复 UI + 弹汇总 + 发布事件。"""
        self._force_finish_progress()
        self._set_suppress_dialogs(False)
        self._set_query_btn_enabled(True)
        self._set_download_btn_enabled(True)
        self._project_mark_dirty()
        self._show_auto_run_summary()
        self._clear_table()
        self._parsed_results.clear()
        EventBus.instance().publish("auto.pipeline.finished", report)

    # ── 汇总弹窗 ─────────────────────────────────────────────

    def _build_auto_summary_message(self, results: list[Any]) -> tuple[str, list[str]]:
        """委托 AutoFlowEngine 统计，Handler 负责 i18n 格式化。"""
        stats = AutoFlowEngine.build_summary_stats(results)

        manual_all: list[str] = []
        for item in stats["manual_all"]:
            if item["reason"] == "not_found":
                manual_all.append(f"{item['number']}  {_('auto_run_manual_row_not_found')}")
            else:
                manual_all.append(f"{item['number']}  {_('auto_run_manual_row_adopted')}")

        msg = (
            _("auto_run_summary_total").format(total=stats["total"])
            + "\n\n"
            + _("auto_run_summary_found").format(count=stats["found_count"])
            + "\n"
            + _("auto_run_summary_not_found").format(count=stats["not_found_count"])
            + "\n"
            + _("auto_run_summary_expired").format(count=stats["expired_count"])
            + "\n"
            + _("auto_run_summary_adopted").format(count=stats["adopted_count"])
        )
        return msg, manual_all

    def _show_auto_summary_dialog(self, msg: str, manual_all: list[str]) -> None:
        """构建汇总弹窗：消息标签 + 待处理列表 + 导出按钮。"""
        dlg = QDialog(self._parent)
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
            """内部函数：根据格式导出汇总数据到文件（txt 或 csv）。"""
            filter_str = _("file_filter_csv") if fmt == "csv" else _("file_filter_txt")
            path, _ignored = QFileDialog.getSaveFileName(
                None, _("dialog_export_summary"), f"auto_run_summary.{fmt}", filter_str
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8-sig") as f:
                    if fmt == "csv":
                        w = csv.writer(f)
                        w.writerow([_("csv_header_std_number"), _("csv_header_std_name"), _("csv_header_reason")])
                        for item in manual_all:
                            parts = item.split("  ")
                            w.writerow(parts if len(parts) >= 2 else [item, "", ""])
                    else:
                        f.write(_("auto_run_manual_txt_header"))
                        f.write("\n".join(manual_all))
                self._status_cb(f"已导出: {path}")
            except OSError as e:
                logger.error("导出汇总失败: %s", e)

        btn_txt.clicked.connect(lambda: _export("txt"))
        btn_csv.clicked.connect(lambda: _export("csv"))
        btn_close.clicked.connect(dlg.accept)
        dlg.exec()

    def _show_auto_run_summary(self) -> None:
        """自动运行完成后弹出汇总统计。"""
        results = self._parsed_results
        if not results:
            return

        msg, manual_all = self._build_auto_summary_message(results)
        self._show_auto_summary_dialog(msg, manual_all)
