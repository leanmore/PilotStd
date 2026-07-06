# pilotstd/ui/controllers/query/mixin.py
# 核心查询逻辑 — 从 query_mixin.py 拆分

import logging
from typing import Any

from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class QueryCoreMethods:
    """核心查询执行 + 表格刷新方法。"""

    def _on_query_result_ready(self: Any, idx: int, result: Any) -> None:
        """实时刷新表格行（字段回写由 manager._classify_after_query 统一完成）。"""
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
            item = self.work_table.item(row, col)
            if item:
                item.setText(text)

        status_item = self.work_table.item(row, 4)
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

    def _on_query_batch_ready(self: Any, batch: list[Any]) -> None:
        """批量处理查询结果：一次刷新多行表格，减少 Qt 布局计算次数。"""
        for idx, result in batch:
            self._on_query_result_ready(idx, result)

    def _on_query(self: Any) -> None:
        if not self._mgr_ready:
            return
        if not self._parsed_results:
            from ....i18n import _

            choice = self._stage_prereq_dialog(_("title_hint"), _("msg_scan_prereq"), _("task_scan"))
            if choice == "run_prereq":
                self._run_scan(self._get_selected_path())
                return
            if choice == "cancel":
                return

        total = len(self._parsed_results)
        if total > 0:
            plan = self._mgr.plan_batch(total)
            csres_count = sum(c for s, c in plan if s == "csres")
            if csres_count > 0:
                self._mgr.get_quota_info()
                from ....i18n import _

                msg = _("query_quota_msg").format(total)
                from PyQt6.QtWidgets import QMessageBox

                reply = self._question_dlg(_("query_quota_title"), msg)
                if reply != QMessageBox.StandardButton.Yes:
                    return

        from ...i18n import _

        self.status_changed.emit(_("status_querying"))
        self.btn_query.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_changed.emit(0)

        for row in range(self.work_table.rowCount()):
            item = self.work_table.item(row, 1)
            if item:
                item.setText("查询中...")

        self.btn_query.setEnabled(False)
        self.btn_auto.setEnabled(False)

        def on_progress(current: int) -> None:
            self._check_pause()
            self.progress_changed.emit(current)

        from ...workers import QueryWorker

        self._query_worker = QueryWorker(self._mgr, self._parsed_results, pause_event=self._pause_event, parent=self)
        self._query_worker.batch_ready.connect(self._on_query_batch_ready)
        self._query_worker.progress.connect(on_progress)
        self._query_worker.error.connect(lambda msg: self._notify_worker_error("query", msg))

        def on_query_finished(_results: Any) -> None:
            self.btn_query.setEnabled(True)
            self.btn_auto.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self._show_query_summary()

        def on_query_error(msg: str) -> None:
            self.btn_query.setEnabled(True)
            self.btn_auto.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.status_changed.emit(f"查询失败: {msg}")
            logging.getLogger(__name__).error(f"查询线程异常: {msg}")

        self._query_worker.finished_signal.connect(on_query_finished)
        self._query_worker.error.connect(on_query_error)
        self._query_worker.start()
