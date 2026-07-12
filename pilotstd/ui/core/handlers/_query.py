# pilotstd/ui/core/handlers/_query.py
"""QueryUIHandler — 查询 UI 状态管理（Core + Pending）。"""

from __future__ import annotations

import csv
import logging
import re
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QTableWidget,
    QWidget,
)

if TYPE_CHECKING:
    from ....core.config import ConfigManager

from ....i18n import _ as tr
from ....models import ParsedStdInfo
from ...pending_query_dialog import PendingQueryDialog
from ...workers import QueryWorker, RowUpdate
from ._query_summary import QuerySummaryHandler

logger = logging.getLogger(__name__)


class QueryUIHandler:
    """查询 UI 状态管理（Core + Pending）。"""

    def __init__(
        self,
        mgr: Any,
        config: ConfigManager,
        pause_event: Any,
        parent_widget: QWidget | None,
        work_table: QTableWidget,
        parsed_results: list[ParsedStdInfo],
        # 回调依赖
        add_table_row: Callable[[RowUpdate], None],
        clear_table: Callable[[], None],
        find_row_by_seq: Callable[[int], int],
        question_dlg: Callable[[str, str], int],
        stage_prereq_dialog: Callable[[str, str, str], str],
        show_stage_dialog: Callable[..., None],
        register_task: Callable[..., None],
        status_callback: Callable[[str], None],
        progress_callback: Callable[[int], None],
        reset_progress: Callable[[], None],
        force_finish_progress: Callable[[], None],
        suppress_dialogs: Callable[[], bool] | None = None,
        project_mark_dirty: Callable[[], None] | None = None,
        notify_worker_error: Callable[[str, str], None] | None = None,
        # 外部流程委托
        run_scan: Callable[[str], None] | None = None,
        get_selected_path: Callable[[], str] | None = None,
        on_download: Callable[[], None] | None = None,
    ) -> None:
        self.__init_tr(
            mgr=mgr,
            config=config,
            pause_event=pause_event,
            parent=parent_widget,
            work_table=work_table,
            parsed_results=parsed_results,
            add_table_row=add_table_row,
            clear_table=clear_table,
            find_row_by_seq=find_row_by_seq,
            question_dlg=question_dlg,
            stage_prereq_dialog=stage_prereq_dialog,
            show_stage_dialog=show_stage_dialog,
            register_task=register_task,
            status_callback=status_callback,
            progress_callback=progress_callback,
            reset_progress=reset_progress,
            force_finish_progress=force_finish_progress,
            suppress_dialogs=suppress_dialogs,
            project_mark_dirty=project_mark_dirty,
            notify_worker_error=notify_worker_error,
            run_scan=run_scan,
            get_selected_path=get_selected_path,
            on_download=on_download,
        )

    def __init_tr(
        self,
        mgr: Any,
        config: ConfigManager,
        pause_event: Any,
        parent: QWidget | None,
        work_table: QTableWidget,
        parsed_results: list[ParsedStdInfo],
        # 回调依赖
        add_table_row: Callable[[RowUpdate], None],
        clear_table: Callable[[], None],
        find_row_by_seq: Callable[[int], int],
        question_dlg: Callable[[str, str], int],
        stage_prereq_dialog: Callable[[str, str, str], str],
        show_stage_dialog: Callable[..., None],
        register_task: Callable[..., None],
        status_callback: Callable[[str], None],
        progress_callback: Callable[[int], None],
        reset_progress: Callable[[], None],
        force_finish_progress: Callable[[], None],
        suppress_dialogs: Callable[[], bool] | None = None,
        project_mark_dirty: Callable[[], None] | None = None,
        notify_worker_error: Callable[[str, str], None] | None = None,
        # 外部流程委托
        run_scan: Callable[[str], None] | None = None,
        get_selected_path: Callable[[], str] | None = None,
        on_download: Callable[[], None] | None = None,
    ) -> None:
        self._mgr = mgr
        self._config = config
        self._pause_event = pause_event
        self._parent = parent
        self._work_table = work_table
        self._parsed_results = parsed_results
        self._add_table_row = add_table_row
        self._clear_table = clear_table
        self._find_row_by_seq = find_row_by_seq
        self._question_dlg = question_dlg
        self._stage_prereq_dialog = stage_prereq_dialog
        self._show_stage_dialog = show_stage_dialog
        self._register_task = register_task
        self._status_cb = status_callback
        self._progress_cb = progress_callback
        self._reset_progress = reset_progress
        self._force_finish_progress = force_finish_progress
        self._suppress_dialogs = suppress_dialogs
        self._project_mark_dirty = project_mark_dirty
        self._notify_worker_error = notify_worker_error
        self._run_scan_cb = run_scan
        self._get_selected_path_cb = get_selected_path
        self._on_download_cb = on_download
        self._query_worker: QueryWorker | None = None
        # 汇总弹窗委托
        self._summary = QuerySummaryHandler(
            mgr=mgr,
            parent=parent,
            work_table=work_table,
            parsed_results=parsed_results,
            suppress_dialogs=suppress_dialogs,
            register_task=register_task,
            project_mark_dirty=project_mark_dirty,
            status_cb=status_callback,
            on_download_cb=on_download,
            export_pending_csv=self.export_pending_csv,
            write_pending_to_db=self.write_pending_to_db,
        )

    def stop_workers(self) -> None:
        """停止正在运行的查询 Worker。"""
        w = self._query_worker
        if w is not None and w.isRunning():
            w.stop()
            w.quit()
            if not w.wait(5000):
                w.terminate()
                w.wait()

    # ═══════════════════════════════════════════════════════
    # Core — 核心查询执行
    # ═══════════════════════════════════════════════════════

    def on_query(self) -> None:
        """查询主入口：前置准备 → Worker 创建 → 信号连接。"""
        if not self._parsed_results:
            choice = self._stage_prereq_dialog(tr("title_hint"), tr("msg_scan_prereq"), tr("task_scan"))
            if choice == "run_prereq" and self._run_scan_cb:
                path = self._get_selected_path_cb() if self._get_selected_path_cb else ""
                self._run_scan_cb(path)
                return
            if choice == "cancel":
                return

        total = len(self._parsed_results)
        if total > 0:
            plan = self._mgr.plan_batch(total)
            csres_count = sum(c for s, c in plan if s == "csres")
            if csres_count > 0:
                self._mgr.get_quota_info()
                msg = tr("query_quota_msg").format(total)
                reply = self._question_dlg(tr("query_quota_title"), msg)
                if reply != QMessageBox.StandardButton.Yes:
                    return

        self._status_cb(tr("work_status_querying"))
        if self._reset_progress:
            self._reset_progress()

        for row in range(self._work_table.rowCount()):
            item = self._work_table.item(row, 1)
            if item:
                item.setText("查询中...")

        def on_progress(current: int) -> None:
            if self._progress_cb:
                self._progress_cb(current)

        self._query_worker = QueryWorker(
            self._mgr, self._parsed_results, pause_event=self._pause_event, parent=self._parent
        )
        self._query_worker.batch_ready.connect(self.on_query_batch_ready)
        self._query_worker.progress.connect(on_progress)
        if self._notify_worker_error:
            self._query_worker.error.connect(
                lambda msg: self._notify_worker_error("query", msg)  # type: ignore[misc]
            )

        def on_query_finished(_results: Any) -> None:
            if self._force_finish_progress:
                self._force_finish_progress()
            self.show_query_summary()

        def on_query_error(msg: str) -> None:
            self._status_cb(f"查询失败: {msg}")
            logger.error("查询线程异常: %s", msg)

        self._query_worker.finished_signal.connect(on_query_finished)
        self._query_worker.error.connect(on_query_error)
        self._query_worker.start()

    def on_query_result_ready(self, idx: int, result: Any) -> None:
        """实时刷新表格行（由 worker 信号触发）。"""
        parsed = self._parsed_results[idx]
        source_label = getattr(result, "source_site", "") or "未知"

        row = self._find_row_by_seq(idx + 1)
        if row < 0:
            return
        cells = [
            (1, f"已查询({source_label})"),
            (3, result.standard_name or parsed.std_name),
            (4, result.status),
            (5, result.replaces if result.replaces != "网站无此分类" else ""),
            (6, result.publish_date if result.publish_date != "网站无此分类" else ""),
            (7, result.implementation_date if result.implementation_date != "网站无此分类" else ""),
            (8, result.responsible_dept if result.responsible_dept != "网站无此分类" else ""),
            (9, "采标" if result.is_adopted else ""),
        ]
        for col, text in cells:
            if text:
                item = self._work_table.item(row, col) or None
                if item:
                    item.setText(str(text))

        status_item = self._work_table.item(row, 4)
        if status_item:
            s = result.status
            if s in ("现行",):
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif s == "即将实施":
                status_item.setForeground(Qt.GlobalColor.blue)
            elif s in ("废止", "已废止", "作废"):
                status_item.setForeground(Qt.GlobalColor.red)
            elif s == "待确认":
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            if not result.is_downloadable and s not in ("废止", "已废止", "作废", "待确认"):
                status_item.setForeground(Qt.GlobalColor.darkYellow)

    def on_query_batch_ready(self, batch: list[Any]) -> None:
        """批量处理查询结果。"""
        for idx, result in batch:
            self.on_query_result_ready(idx, result)

    # ═══════════════════════════════════════════════════════
    # Pending — 待确认管理
    # ═══════════════════════════════════════════════════════

    def export_pending_csv(self, save_status: QLabel | None = None) -> str | None:
        """导出待确认条目为 CSV。返回保存路径，失败返回 None。"""
        rows = self._mgr.get_pending_items()
        if not rows:
            if save_status is not None:
                save_status.setText(tr("msg_no_pending_items"))
                save_status.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            return None

        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            None,
            tr("dialog_save_pending"),
            f"pending_standards_{ts}.csv",
            tr("file_filter_csv"),
        )
        if not path:
            return None

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        tr("query_pending_col_std_number"),
                        tr("query_pending_col_source_filename"),
                        tr("query_pending_col_web_name"),
                        tr("query_pending_col_local_year"),
                        tr("query_pending_col_web_number"),
                        tr("query_pending_col_status"),
                        tr("query_pending_col_confidence"),
                        tr("query_pending_col_source_site"),
                    ]
                )
                for row in rows:
                    std_num = row.get("standard_number", "")
                    year_match = re.search(r"[-–](\d{4})$", std_num)
                    year = year_match.group(1) if year_match else ""
                    writer.writerow(
                        [
                            std_num,
                            row.get("std_name", ""),
                            row.get("found_name", ""),
                            year,
                            row.get("found_number", ""),
                            row.get("effect_status", ""),
                            str(row.get("score", "")),
                            row.get("source_site", ""),
                        ]
                    )
            if save_status is not None:
                save_status.setText(f"已保存: pending_standards_{ts}.csv")
                save_status.setStyleSheet("color: #2a7d2a; font-size: 9pt;")
            return path
        except OSError as e:
            if save_status is not None:
                save_status.setText(f"保存失败: {e}")
                save_status.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            return None

    def on_pending_query(self) -> None:
        """待确认二次查询入口。"""
        try:
            self.do_pending_query()
        except Exception as e:
            logger.exception("待确认查询异常")
            QMessageBox.critical(
                self._parent,
                tr("title_error"),
                tr("error_pending_query_failed").format(error=e),
            )

    def parse_pending_csv(self, path: str) -> tuple[list[ParsedStdInfo], list[str]]:
        """解析待确认 CSV，返回 (parsed_list, failed_names)。"""
        parsed_list: list[ParsedStdInfo] = []
        failed_names: list[str] = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return parsed_list, failed_names
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if not row or not row[0].strip():
                continue
            std_num = row[0].strip()
            try:
                parsed = self._mgr.parse_standard_number(std_num + ".pdf")
            except Exception as e:
                logger.warning("解析标准号失败: %s — %s", std_num, e)
                failed_names.append(std_num)
                continue
            if parsed:
                parsed.std_name = row[1].strip() if len(row) > 1 and row[1].strip() else parsed.std_name
                parsed_list.append(parsed)
            else:
                failed_names.append(std_num)
        return parsed_list, failed_names

    def do_pending_query(self) -> None:
        """完整的待确认查询流程：打开 CSV → 解析 → PendingQueryDialog → 填充表格。"""
        if self._parsed_results:
            QMessageBox.warning(self._parent, tr("title_hint"), tr("workspace_not_empty"))
            return

        path, _ = QFileDialog.getOpenFileName(self._parent, tr("dialog_import_pending"), "", tr("file_filter_csv"))
        if not path:
            return

        parsed_list, failed_names = self.parse_pending_csv(path)
        if not parsed_list:
            QMessageBox.warning(self._parent, tr("title_hint"), tr("csv_no_standards"))
            return

        msg = tr("msg_csv_parse_result").format(count=len(parsed_list))
        if failed_names:
            msg += f"，{tr('msg_csv_unrecognized').format(count=len(failed_names))}:\n"
            msg += "\n".join(failed_names[:5])
            if len(failed_names) > 5:
                msg += f"\n... 等共 {len(failed_names)} 条"
        msg += "\n\n是否继续？"
        reply = self._question_dlg(tr("title_pending_query"), msg)
        if reply != QMessageBox.StandardButton.Yes:
            self._status_cb(tr("status_pending_cancelled"))
            return

        dlg = PendingQueryDialog(self._mgr, parsed_list, self._parent)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._status_cb(tr("status_pending_cancelled"))
            return

        results = dlg.get_results()
        self._mgr._classifier.classify(
            [r for __, r in results],
            parsed_list,
            self._mgr._download_list,
            self._mgr._expire_list,
            self._mgr._pending_list,
        )
        self._mgr._queried_items = parsed_list
        self._clear_table()
        self._parsed_results.clear()
        self._parsed_results.extend(parsed_list)

        for i, p in enumerate(self._parsed_results):
            self._add_table_row(
                RowUpdate(
                    seq=self._work_table.rowCount() + 1,
                    parsed=p,
                    work_status="已查询",
                    total=len(self._parsed_results),
                )
            )

        total = len(self._parsed_results)
        found = sum(1 for p in self._parsed_results if p.found_name)
        self._status_cb(f"待确认查询完成: {found}/{total}")
        self.show_query_summary()

    def write_pending_to_db(self, pending_items: list[Any]) -> None:
        """将待确认项写入 pending_lookup 表。"""
        self._mgr.record_pending(pending_items)

    def resolve_pending_in_db(self, pending_items: list[Any], resolution: str) -> None:
        """标记待确认项为已处理。"""
        self._mgr.resolve_pending(pending_items, resolution)

    # ═══════════════════════════════════════════════════════
    # Summary — 委托给 QuerySummaryHandler
    # ═══════════════════════════════════════════════════════

    def show_query_summary(self) -> None:
        """委托给 QuerySummaryHandler 构建汇总弹窗。"""
        self._summary.show_query_summary()
