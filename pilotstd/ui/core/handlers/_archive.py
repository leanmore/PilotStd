# pilotstd/ui/core/handlers/_archive.py
"""ArchiveUIHandler — 归档 UI 状态管理，替代 ArchiveMixin。

重构后纯逻辑委托给 self._engine（ArchiveFlowEngine），
Worker 创建委托给 self._factory（ArchiveWorkerFactory）。
Handler 仅保留 Qt 控件交互、对话框、信号连接。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtWidgets import QMessageBox, QTableWidget

if TYPE_CHECKING:
    from ....core.config import ConfigManager

from ....i18n import _
from ...workers import RowUpdate
from ..event_bus import EventBus
from .archive_flow_engine import ArchiveFlowEngine
from .archive_worker_factory import ArchiveCallbacks, ArchiveWorkerFactory

logger = logging.getLogger(__name__)


class ArchiveUIHandler:
    """归档 UI 状态管理。

    职责：归档前置检查（冲突预检）、调用 mgr.archive_standards、
    调用 mgr.normalize_files_stream、表格更新、结果汇总。
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
        suppress_dialogs: Callable[[], bool],
        stage_prereq_dialog: Callable[..., str],
        show_stage_dialog: Callable[..., None],
        question_dlg: Callable[..., Any],
        register_task: Callable[..., None],
        project_mark_dirty: Callable[[], None],
        reset_progress: Callable[[], None],
        force_finish_progress: Callable[[], None],
        add_table_row: Callable[..., None],
        clear_table: Callable[[], None],
        update_button_states: Callable[[], None],
        find_row_by_seq: Callable[[int], int],
        run_scan_cb: Callable[[str], None],
        run_query_cb: Callable[[], None],
        get_selected_path_cb: Callable[[], str],
        on_raw_progress: Callable[[int, int], None],
    ) -> None:
        self._mgr = mgr
        self._config = config
        self._pause_event = pause_event
        self._parent = parent_widget
        self._work_table = work_table
        self._parsed_results = parsed_results
        self._status_cb = status_callback
        self._suppress_dialogs = suppress_dialogs
        self._stage_prereq_dialog = stage_prereq_dialog
        self._show_stage_dialog = show_stage_dialog
        self._question_dlg = question_dlg
        self._register_task = register_task
        self._project_mark_dirty = project_mark_dirty
        self._reset_progress = reset_progress
        self._force_finish_progress = force_finish_progress
        self._add_table_row = add_table_row
        self._clear_table = clear_table
        self._update_button_states = update_button_states
        self._find_row_by_seq = find_row_by_seq
        self._run_scan_cb = run_scan_cb
        self._run_query_cb = run_query_cb
        self._get_selected_path_cb = get_selected_path_cb
        self._on_raw_progress = on_raw_progress
        # 纯逻辑引擎
        self._engine = ArchiveFlowEngine()
        # Worker 工厂
        self._factory = ArchiveWorkerFactory(mgr, config, pause_event, parent_widget)
        self._archive_worker: Any = None
        self._normalize_worker: Any = None
        self._archive_results: list[tuple[int, str]] = []

    # ── 公开方法 ─────────────────────────────────────────────

    def stop_workers(self) -> None:
        """停止正在运行的归档/规范化 Worker。"""
        for w in (self._archive_worker, self._normalize_worker):
            if w is not None and w.isRunning():
                w.stop()
                w.quit()
                if not w.wait(5000):
                    w.terminate()
                    w.wait()

    def notify_worker_error(self, worker_name: str, error_msg: str) -> None:
        """Worker 异常时弹出本地通知。"""
        from ....platform.notify import NotifyService

        NotifyService.get().show("工作线程异常", f"{worker_name}: {error_msg}", duration=5000)

    def on_normalize(self) -> None:
        """规范化：标准名称缺失补全 → 冲突处理 → 后台计算规范文件名。"""
        print(f"[TRACE] on_normalize: id={id(self._parsed_results)} len={len(self._parsed_results)}")
        if not self._parsed_results:
            choice = self._stage_prereq_dialog(_("title_hint"), _("msg_scan_prereq"), _("task_scan"))
            if choice == "run_prereq":
                self._run_scan_cb(self._get_selected_path_cb())
                return
            if choice == "cancel":
                return

        # 纯逻辑：查找缺失名称
        missing = self._engine.find_missing_names(self._parsed_results)
        if missing:
            more = f"\n... 还有 {len(missing) - 5} 条" if len(missing) > 5 else ""
            reply = self._question_dlg(
                _("title_missing_name"),
                _("msg_missing_name").format(count=len(missing), list="\n".join(missing[:5]), more=more),
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._run_query_cb()

        # 名称冲突检测
        conflicts = [p for p in self._parsed_results if getattr(p, "stage_status", "") == "name_conflict"]
        if conflicts and not self._suppress_dialogs():
            resolved = self._show_name_conflict_dialog(conflicts)
            for p in conflicts:
                if getattr(p, "stage_status", "") == "name_conflict":
                    self._mgr.record_pending([p])
            for p in resolved:
                p.stage_status = "archive_ready"
        elif conflicts:
            self._mgr.record_pending(conflicts)

        self._clear_table()
        self._reset_progress()

        # 工厂：创建规范化 Worker
        callbacks = ArchiveCallbacks(
            on_batch_ready=self.on_normalize_batch_ready,
            on_progress=lambda pct: (
                self._on_raw_progress(pct, 100),
                self._publish_event("archive.progress", {"pct": pct}),
            ),  # type: ignore[func-returns-value]
            on_error=lambda msg: (
                self.notify_worker_error("normalize", msg),
                self._publish_event("archive.error", {"error": msg}),
            ),
            on_finished=self._make_normalize_finished(),
        )
        self._normalize_worker = self._factory.create_normalize_worker(
            self._parsed_results, callbacks
        )
        self._normalize_worker.start()

    def _make_normalize_finished(self) -> Callable[[], None]:
        def on_finished() -> None:
            self._force_finish_progress()
            count = len(self._parsed_results)
            self._status_cb(_("normalize_complete").format(count))
            self._register_task("规范化", count, count)
            self._publish_event("archive.finished", {"count": count})
            if not self._suppress_dialogs():
                self._show_stage_dialog(
                    _("normalize_results_title"),
                    _("msg_normalize_done").format(count=count),
                    next_action=self.on_save_to_folder,
                    next_label=_("next_step_save"),
                )
        return on_finished

    def on_normalize_batch_ready(self, batch: list[Any]) -> None:
        """批量更新规范化结果到表格。"""
        for idx, parsed, name in batch:
            self._add_table_row(
                RowUpdate(
                    seq=self._work_table.rowCount() + 1,
                    parsed=parsed,
                    work_status="已规范化",
                    std_name_override=name,
                    total=len(self._parsed_results),
                )
            )

    def on_save_to_folder(self) -> None:
        """将文件以规范名称归档到标准库目录。后台线程执行文件操作。"""
        if not self._parsed_results:
            choice = self._stage_prereq_dialog(_("title_hint"), _("msg_scan_prereq"), _("task_scan"))
            if choice == "run_prereq":
                self._run_scan_cb(self._get_selected_path_cb())
                return
            if choice == "cancel":
                return

        root_dir = self._engine.get_library_root_from_config(self._config)
        proceed, overwrite_all = self._check_archive_conflicts(root_dir)
        if not proceed:
            return

        self._reset_progress()
        # 工厂：创建归档 Worker
        self._archive_results = []
        callbacks = ArchiveCallbacks(
            on_batch_ready=self.on_archive_batch_ready,
            on_progress=lambda pct: self._on_raw_progress(pct, 100),
            on_error=lambda msg: self.notify_worker_error("archive", msg),
            on_finished=lambda: self._handle_archive_completed(root_dir),
        )
        self._archive_worker = self._factory.create_archive_worker(
            self._parsed_results, root_dir, overwrite_all, callbacks
        )
        self._archive_worker.start()

    def on_archive_batch_ready(self, batch: list[Any]) -> None:
        """批量更新归档结果到表格。"""
        self._archive_results.extend(batch)
        for idx, status in batch:
            row = self._find_row_by_seq(idx + 1)
            if row < 0:
                continue
            item = self._work_table.item(row, 1)
            if item:
                item.setText(status)

    # ── 内部方法 ─────────────────────────────────────────────

    def _check_archive_conflicts(self, root_dir: str) -> tuple[bool, bool]:
        """冲突预检：扫描所有文件的源→目标路径，弹窗询问覆盖策略。

        返回 (proceed, overwrite_all)。proceed=False 表示用户取消。
        """
        from ...workers import ArchiveWorker

        # 纯逻辑：检测冲突
        conflicts = self._engine.detect_file_conflicts(
            self._parsed_results, root_dir, self._config, ArchiveWorker.target_path
        )

        if not conflicts or self._suppress_dialogs():
            return True, False

        # 纯逻辑：格式化消息
        msg = self._engine.format_conflict_message(conflicts)
        reply = QMessageBox.question(
            self._parent,
            _("title_file_exists"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False, False
        return True, reply == QMessageBox.StandardButton.Yes

    def _handle_archive_completed(self, root_dir: str) -> None:
        """归档完成回调：统计结果 + 写入 file_index + 过期合并 + 汇总弹窗。"""
        self._force_finish_progress()
        # 纯逻辑：统计
        saved, skipped = self._engine.count_archive_results(self._archive_results)
        self._status_cb(_("save_complete").format(saved, skipped))
        self._register_task("保存", len(self._archive_results), saved, skipped)

        for idx, status in self._archive_results:
            if status != "已归档":
                continue
            parsed = self._parsed_results[idx]
            if parsed.source_path:
                st = self._engine.determine_status_label(parsed.effect_status)
                self._mgr.upsert_file_index(
                    file_path=parsed.source_path,
                    logical_code=parsed.logical_code,
                    number=parsed.number,
                    year=parsed.year,
                    part=parsed.part,
                    std_name=parsed.std_name,
                    status=st,
                )

        self._merge_expire_from_source(root_dir)
        if not self._suppress_dialogs():
            # 纯逻辑：格式化跳过详情
            skip_details = self._engine.format_skip_details(
                self._archive_results, self._parsed_results
            )
            detail_text = ""
            if skip_details:
                shown = skip_details[:20]
                more = f"\n  ... {len(skip_details) - 20} more" if len(skip_details) > 20 else ""
                detail_text = (
                    _("msg_archive_skip_detail").format(lines="\n".join(shown) + more)
                    if more
                    else _("msg_archive_skip_detail").format(lines="\n".join(shown))
                )
            self._show_stage_dialog(
                _("save_results_title"),
                _("msg_save_done").format(saved=saved, skipped=skipped, detail=detail_text),
                next_action=None,
                next_label="",
            )
            self._clear_table()
            self._parsed_results.clear()

    def _merge_expire_from_source(self, root_dir: str) -> None:
        """源文件夹中过期作废目录合并到标准库（委托 manager）。"""
        merged = self._mgr.merge_expire_from_source(root_dir, self._parsed_results)
        if merged:
            self._status_cb(f"源过期目录合并: {merged} 个文件")

    def _auto_move_expired(self) -> int:
        """查询后将废止标准自动移入过期作废/（委托 manager）。"""
        expired = self._engine.filter_by_action(self._parsed_results, "expire")
        if not expired:
            return 0
        result = self._mgr.handle_expired(expired)
        moved = result.get("moved", 0)
        if moved:
            self._status_cb(f"查询完成: 已自动将 {moved} 个废止标准移入过期作废/")
        return moved

    def _show_name_conflict_dialog(self, conflicts: list[Any]) -> list[Any]:
        """名称冲突弹窗：逐条让用户选择。返回用户已确认的条目列表。"""
        resolved: list[Any] = []
        for p in conflicts[:10]:
            src = getattr(p, "source_name", "") or "（无）"
            qry = getattr(p, "found_name", "") or "（无）"
            full_num = p.get_full_number()
            msg = f"标准号: {full_num}\n\n源文件名称: {src}\n网站查询名称: {qry}\n\n请选择归档使用的名称:"
            dlg = QMessageBox(self._parent)
            dlg.setWindowTitle(_("title_name_conflict"))
            dlg.setText(msg)
            dlg.setIcon(QMessageBox.Icon.Question)
            btn_src = dlg.addButton(_("btn_use_source_name"), QMessageBox.ButtonRole.AcceptRole)
            btn_qry = dlg.addButton(_("btn_use_query_name"), QMessageBox.ButtonRole.YesRole)
            dlg.addButton(_("btn_cancel"), QMessageBox.ButtonRole.RejectRole)
            dlg.exec()
            clicked = dlg.clickedButton()
            if clicked == btn_src:
                p.final_name = src
                p.std_name = src
                p.stage_status = ""
                resolved.append(p)
            elif clicked == btn_qry:
                p.final_name = qry
                p.std_name = qry
                p.stage_status = ""
                resolved.append(p)
            dlg.deleteLater()
        return resolved

    # ── 事件发布 ─────────────────────────────────────────────

    @staticmethod
    def _publish_event(event_name: str, data: Any) -> None:
        """封装事件发布。"""
        EventBus.instance().publish(event_name, data)
