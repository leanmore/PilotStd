# pilotstd/ui/core/handlers/_query.py
"""QueryUIHandler — 查询 UI 状态管理（Core + Pending）。

重构后 __init__ 从 30+ 参数收敛为 13 个（1 聚合接口 + 12 独立参数）。
内部通过 self._deps.{table,dialog,task,worker_factory} 访问依赖。
纯逻辑委托给 self._engine（QueryFlowEngine）。
"""

from __future__ import annotations

import csv
import logging
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
)

if TYPE_CHECKING:
    from ....core.config import ConfigManager

from ....i18n import _ as tr
from ....models import ParsedStdInfo
from ...pending_query_dialog import PendingQueryDialog
from ..event_bus import EventBus
from ._query_summary import QuerySummaryHandler
from .protocols import IQueryDependencies, QueryCallbacks
from .query_flow_engine import QueryFlowEngine

logger = logging.getLogger(__name__)

# hex → Qt.GlobalColor 映射（引擎返回 hex 字符串，Handler 负责转换为 Qt 枚举着色）
_STATUS_HEX_TO_QT: dict[str, Qt.GlobalColor] = {
    "#008000": Qt.GlobalColor.darkGreen,
    "#0000ff": Qt.GlobalColor.blue,
    "#ff0000": Qt.GlobalColor.red,
    "#808000": Qt.GlobalColor.darkYellow,
}


class QueryUIHandler:
    """查询 UI 状态管理（Core + Pending）。"""

    def __init__(
        self,
        deps: IQueryDependencies,
        config: ConfigManager,
        mgr: Any,
        parsed_results: list[ParsedStdInfo],
        run_scan_cb: Callable[[str], None] | None = None,
        status_changed: Callable[[str], None] | None = None,
        progress_changed: Callable[[int], None] | None = None,
        reset_progress: Callable[[], None] | None = None,
        force_finish_progress: Callable[[], None] | None = None,
        suppress_dialogs: Callable[[], bool] | None = None,
        project_mark_dirty: Callable[[], None] | None = None,
        notify_worker_error: Callable[[str, str], None] | None = None,
        on_download_cb: Callable[[], None] | None = None,
    ) -> None:
        self._deps = deps
        self._config = config
        self._mgr = mgr
        self._parsed_results = parsed_results
        self._run_scan_cb = run_scan_cb
        self._status_changed = status_changed
        self._progress_changed = progress_changed
        self._reset_progress = reset_progress
        self._force_finish_progress = force_finish_progress
        self._suppress_dialogs = suppress_dialogs
        self._project_mark_dirty = project_mark_dirty
        self._notify_worker_error = notify_worker_error
        self._on_download_cb = on_download_cb
        self._query_worker: Any = None
        # 纯逻辑引擎
        self._engine = QueryFlowEngine(config)
        # 汇总弹窗委托
        self._summary = QuerySummaryHandler(
            mgr=mgr,
            parent=deps.table.get_work_table().parentWidget(),
            work_table=deps.table.get_work_table(),
            parsed_results=parsed_results,
            suppress_dialogs=suppress_dialogs,
            register_task=deps.task.register_task,
            project_mark_dirty=project_mark_dirty,
            status_cb=status_changed,
            on_download_cb=on_download_cb,
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

    # ═══════════════════════════════════════════════════════════
    # Core — 核心查询执行
    # ═══════════════════════════════════════════════════════════

    def on_query(self) -> None:
        """查询主入口：前置准备 → Worker 创建 → 信号连接。"""
        if not self._parsed_results:
            choice = self._deps.dialog.stage_prereq_dialog(tr("title_hint"), tr("msg_scan_prereq"), tr("task_scan"))
            if choice == "run_prereq" and self._run_scan_cb:
                path = self._deps.table.get_selected_path()
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
                if not self._deps.dialog.question_dlg(tr("query_quota_title"), msg):
                    return

        if self._status_changed:
            self._status_changed(tr("work_status_querying"))
        if self._reset_progress:
            self._reset_progress()

        wt = self._deps.table.get_work_table()
        for row in range(wt.rowCount()):
            item = wt.item(row, 1)
            if item:
                item.setText("查询中...")

        def on_progress(current: int) -> None:
            """查询进度回调：更新进度条百分比。"""
            if self._progress_changed:
                self._progress_changed(current)

        def on_query_finished(_results: Any) -> None:
            """查询完成回调：强制完成进度条 + 发布事件 + 弹出汇总。"""
            if self._force_finish_progress:
                self._force_finish_progress()
            self._publish_event("query.finished", {"count": len(_results) if _results else 0})
            self.show_query_summary()

        def on_query_error(msg: str) -> None:
            """查询错误回调：更新状态栏 + 记录日志 + 本地通知 + 发布事件。"""
            if self._status_changed:
                self._status_changed(f"查询失败: {msg}")
            logger.error("查询线程异常: %s", msg)
            if self._notify_worker_error:
                self._notify_worker_error("query", msg)
            self._publish_event("query.error", {"error": msg})

        callbacks = QueryCallbacks(
            on_result_ready=self.on_query_result_ready,
            on_batch_ready=self.on_query_batch_ready,
            on_progress=on_progress,
            on_finished=on_query_finished,
            on_error=on_query_error,
        )
        self._query_worker = self._deps.worker_factory.create_query_worker(self._parsed_results, callbacks)
        self._query_worker.start()

    def on_query_result_ready(self, idx: int, result: Any) -> None:
        """实时刷新表格行（由 worker 信号触发）。"""
        parsed = self._parsed_results[idx]
        source_label = getattr(result, "source_site", "") or "未知"

        row = self._deps.table.find_row_by_seq(idx + 1)
        if row < 0:
            return
        wt = self._deps.table.get_work_table()

        # 纯逻辑：构建单元格列表
        cells = self._engine.build_result_cells(result, parsed, source_label)
        for col, text in cells:
            if text:
                item = wt.item(row, col) or None
                if item:
                    item.setText(str(text))

        # 纯逻辑：确定状态颜色 → Handler 负责 Qt 着色
        status_item = wt.item(row, 4)
        if status_item:
            color_hex = self._engine.determine_status_color(result.status, result.is_downloadable)
            qt_color = _STATUS_HEX_TO_QT.get(color_hex)
            if qt_color is not None:
                status_item.setForeground(qt_color)
            elif color_hex:
                logger.warning(
                    "未知状态颜色: status=%s is_downloadable=%s hex=%s",
                    result.status,
                    result.is_downloadable,
                    color_hex,
                )

    def on_query_batch_ready(self, batch: list[Any]) -> None:
        """批量处理查询结果。"""
        for idx, result in batch:
            self.on_query_result_ready(idx, result)

    # ═══════════════════════════════════════════════════════════
    # Pending — 待确认管理
    # ═══════════════════════════════════════════════════════════

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
                writer.writerow(self._engine.build_pending_csv_headers())
                for row in rows:
                    writer.writerow(self._engine.build_pending_csv_row(row))
            if save_status is not None:
                save_status.setText(f"已保存: pending_standards_{ts}.csv")
                save_status.setStyleSheet("color: #2a7d2a; font-size: 9pt;")
            return path
        except OSError as e:
            if save_status is not None:
                save_status.setText(f"保存失败: {e}")
                save_status.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            return None

    # _archived: 此方法未被 UI 调用，实际待确认查询由 parts/_query_ops.py 处理
    def on_pending_query(self) -> None:
        """待确认二次查询入口。"""
        try:
            self.do_pending_query()
        except Exception as e:
            logger.exception("待确认查询异常")
            QMessageBox.critical(
                self._deps.table.get_work_table().parentWidget(),
                tr("title_error"),
                tr("error_pending_query_failed").format(error=e),
            )

    def parse_pending_csv(self, path: str) -> tuple[list[ParsedStdInfo], list[str]]:
        """解析待确认 CSV，委托给 QueryFlowEngine。"""
        return self._engine.parse_csv_content(path, self._mgr.parse_standard_number)

    # _archived: 此方法未被 UI 调用，实际待确认查询由 parts/_query_ops.py 处理
    def do_pending_query(self) -> None:
        """完整的待确认查询流程：打开 CSV → 解析 → PendingQueryDialog → 填充表格。"""
        if self._parsed_results:
            QMessageBox.warning(
                self._deps.table.get_work_table().parentWidget(),
                tr("title_hint"),
                tr("workspace_not_empty"),
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self._deps.table.get_work_table().parentWidget(),
            tr("dialog_import_pending"),
            "",
            tr("file_filter_csv"),
        )
        if not path:
            return

        parsed_list, failed_names = self.parse_pending_csv(path)
        if not parsed_list:
            QMessageBox.warning(
                self._deps.table.get_work_table().parentWidget(),
                tr("title_hint"),
                tr("csv_no_standards"),
            )
            return

        msg = tr("msg_csv_parse_result").format(count=len(parsed_list))
        if failed_names:
            msg += f"，{tr('msg_csv_unrecognized').format(count=len(failed_names))}:\n"
            msg += "\n".join(failed_names[:5])
            if len(failed_names) > 5:
                msg += f"\n... 等共 {len(failed_names)} 条"
        msg += "\n\n是否继续？"
        if not self._deps.dialog.question_dlg(tr("title_pending_query"), msg):
            if self._status_changed:
                self._status_changed(tr("status_pending_cancelled"))
            return

        dlg = PendingQueryDialog(self._mgr, parsed_list, self._deps.table.get_work_table().parentWidget())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            if self._status_changed:
                self._status_changed(tr("status_pending_cancelled"))
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
        self._deps.table.clear_table()
        self._parsed_results.clear()
        self._parsed_results.extend(parsed_list)

        for i, p in enumerate(self._parsed_results):
            self._deps.table.add_table_row(
                {
                    "seq": self._deps.table.get_work_table().rowCount() + 1,
                    "parsed": p,
                    "work_status": "已查询",
                    "total": len(self._parsed_results),
                }
            )

        total = len(self._parsed_results)
        found = sum(1 for p in self._parsed_results if p.found_name)
        if self._status_changed:
            self._status_changed(f"待确认查询完成: {found}/{total}")
        self.show_query_summary()

    def write_pending_to_db(self, pending_items: list[Any]) -> None:
        """将待确认项写入 pending_lookup 表。"""
        self._mgr.record_pending(pending_items)

    def resolve_pending_in_db(self, pending_items: list[Any], resolution: str) -> None:
        """标记待确认项为已处理。"""
        self._mgr.resolve_pending(pending_items, resolution)

    # ═══════════════════════════════════════════════════════════
    # Summary — 委托给 QuerySummaryHandler
    # ═══════════════════════════════════════════════════════════

    def show_query_summary(self) -> None:
        """委托给 QuerySummaryHandler 构建汇总弹窗。"""
        self._summary.show_query_summary()

    # ── 事件发布 ─────────────────────────────────────────────

    @staticmethod
    def _publish_event(event_name: str, data: Any) -> None:
        """封装事件发布，便于统一加日志/监控。"""
        EventBus.instance().publish(event_name, data)
