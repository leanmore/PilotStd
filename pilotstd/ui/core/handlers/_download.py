# pilotstd/ui/core/handlers/_download.py
"""DownloadUIHandler — 下载 UI 状态管理，替代 DownloadMixin。

薄包装层：Worker 管理 + Qt 控件交互。纯逻辑委托给 DownloadFlowEngine。
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidget

if TYPE_CHECKING:
    from ....core.config import ConfigManager

from ....i18n import _
from ...workers import DownloadWorker, RowUpdate
from ..event_bus import EventBus
from .download_flow_engine import DownloadFlowEngine

logger = logging.getLogger(__name__)


class DownloadUIHandler:
    """下载 UI 状态管理，替代 DownloadMixin。

    职责：下载前置检查、调用 mgr.download_stream、表格更新、结果弹窗。
    通过显式依赖注入替代多重继承，共享 UI 操作（弹窗/进度）以回调方式注入。
    """

    def __init__(
        self,
        mgr: Any,
        config: ConfigManager,
        pause_event: Any,
        parent_widget: Any,
        work_table: QTableWidget,
        status_callback: Callable[[str], None],
        progress_callback: Callable[[int], None],
        show_stage_dialog: Callable[..., None],
        question_dlg: Callable[..., Any],
        stage_prereq_dialog: Callable[..., str],
        register_task: Callable[..., None],
        project_mark_dirty: Callable[[], None],
        suppress_dialogs: Callable[[], bool],
        add_table_row: Callable[..., None],
        find_row_by_seq: Callable[[int], int],
    ) -> None:
        self._mgr = mgr
        self._config = config
        self._pause_event = pause_event
        self._parent = parent_widget
        self._work_table = work_table
        self._status_cb = status_callback
        self._progress_cb = progress_callback
        self._show_stage_dialog = show_stage_dialog
        self._question_dlg = question_dlg
        self._stage_prereq_dialog = stage_prereq_dialog
        self._register_task = register_task
        self._project_mark_dirty = project_mark_dirty
        self._suppress_dialogs = suppress_dialogs
        self._add_table_row = add_table_row
        self._find_row_by_seq = find_row_by_seq
        self._download_worker: DownloadWorker | None = None
        self._engine = DownloadFlowEngine()

    # ── 公开方法 ─────────────────────────────────────────────

    def on_download(self) -> None:
        """下载处理：前置检查 → 表格准备 → Worker 启动。"""
        # 第一步：前置检查和准备下载列表
        ok, download_list = self.prepare_download()
        if not ok:
            return

        to_download = [(i, p) for i, p in enumerate(download_list)]
        total = len(to_download)
        # 筛选发布不满阈值的标准，加入等待队列
        too_new_set = self.filter_too_new_standards(download_list)

        self._status_cb(_("download_in_progress"))
        # 重置表格并预填充下载列表
        self.reset_ui_for_download(download_list, total)

        # 创建下载 Worker 并连接信号
        self._download_worker = DownloadWorker(
            self._mgr, download_list, pause_event=self._pause_event, parent=self._parent
        )

        def on_worker_progress(pct: int) -> None:
            self._status_cb(f"下载进度: {pct}%")

        self._download_worker.progress.connect(on_worker_progress)
        self._download_worker.progress.connect(lambda pct: self._publish_event("download.progress", {"pct": pct}))
        self._download_worker.batch_ready.connect(self.on_download_batch_ready)

        def _on_finished() -> None:
            self.on_download_finished(to_download, too_new_set, total, download_list)

        self._download_worker.finished_signal.connect(_on_finished)
        self._download_worker.finished_signal.connect(
            lambda: self._publish_event("download.finished", {"total": total})
        )
        self._download_worker.error.connect(self.on_download_error)
        self._download_worker.error.connect(lambda msg: self._publish_event("download.error", {"error": msg}))
        self._download_worker.start()

    def on_import_download(self) -> None:
        """从文件导入标准号列表并直接下载。"""
        path, _filter = QFileDialog.getOpenFileName(
            self._parent,
            _("dialog_select_file"),
            "",
            _("file_filter_txt") + ";;" + _("file_filter_csv") + ";;" + _("file_filter_std"),
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            QMessageBox.warning(self._parent, _("title_import_failed"), str(e))
            return

        # CSV 文件走 Engine 解析
        if path.lower().endswith(".csv"):
            records = self._engine.parse_download_csv(content)
            if not records:
                QMessageBox.information(self._parent, _("title_hint"), _("csv_empty"))
                return
            first_key = list(records[0].keys())[0] if records else ""
            lines = [r.get(first_key, "").strip() for r in records if r.get(first_key, "").strip()]
        else:
            lines = [line.strip() for line in content.splitlines() if line.strip()]

        if not lines:
            QMessageBox.information(self._parent, _("title_hint"), _("csv_empty"))
            return

        # 去重
        items = [{"number": line} for line in lines]
        items = self._engine.deduplicate_downloads(items, "number")
        lines = [item["number"] for item in items]

        self._status_cb(_("download_in_progress"))
        _tasks, stats = self._mgr.download_by_numbers(lines)
        msg = (
            f"{_('download_results_total')}: {stats.total}\n"
            f"{_('download_results_success')}: {stats.success}\n"
            f"{_('download_results_failed')}: {stats.failed}"
        )
        QMessageBox.information(self._parent, _("download_results_title"), msg)
        self._project_mark_dirty()

    def stop_workers(self) -> None:
        """停止正在运行的下载 Worker。"""
        w = self._download_worker
        if w is not None and w.isRunning():
            w.stop()
            w.quit()
            if not w.wait(5000):
                w.terminate()
                w.wait()

    def enqueue_download_wait(self, parsed: Any) -> None:
        """将未到下载期的标准写入下载等待队列。"""
        self._mgr.enqueue_download_wait(parsed)

    def check_download_queue(self) -> list[dict[str, Any]] | None:
        """检查下载等待队列，返回到期项（None 表示无到期项）。"""
        due = self._mgr.get_due_downloads()
        return due if due else None

    # ── 内部方法 ─────────────────────────────────────────────

    def prepare_download(self) -> tuple[bool, Any]:
        """guard 检查 + 获取 download_list + 前置条件对话框。"""
        download_list = self._mgr.get_stage_queue("download")
        if not download_list:
            choice = self._stage_prereq_dialog(_("title_hint"), _("msg_download_prereq"), _("task_query"))
            if choice in ("run_prereq", "cancel"):
                return False, None
        return True, download_list

    def filter_too_new_standards(self, download_list: list) -> set:
        """筛选发布不满阈值的标准，加入等待队列。

        Engine 负责判断哪些标准过新；Handler 负责入队 + 弹窗。
        """
        too_new_set: set = set()
        too_new = self._engine.filter_too_new_standards(download_list)

        too_new_list: list = []
        for orig_idx, p in enumerate(download_list):
            if p in too_new:
                too_new_list.append((orig_idx, p))
                too_new_set.add(orig_idx)
                self._mgr.enqueue_download_wait(p)

        if too_new_list and not self._suppress_dialogs():
            lines = [_("msg_new_std_too_new"), ""]
            for _idx, p in too_new_list[:10]:
                num = getattr(p, "found_number", None) or p.get_full_number()
                lines.append(f"  {num}")
            if len(too_new_list) > 10:
                lines.append(f"  ... {len(too_new_list)} total")
            QMessageBox.information(self._parent, _("title_new_std_unavailable"), "\n".join(lines))
        return too_new_set

    def reset_ui_for_download(self, download_list: list, total: int) -> None:
        """表格重置 + 预填充下载列表。"""
        self._work_table.setRowCount(0)
        for i, p in enumerate(download_list):
            self._add_table_row(RowUpdate(seq=i + 1, parsed=p, work_status="待下载", total=total))

    def update_download_row(self, idx: int, status: str) -> None:
        """更新单行下载状态。"""
        row = self._find_row_by_seq(idx + 1)
        if row < 0:
            return
        item = self._work_table.item(row, 1)
        if item:
            item.setText(status)

    def on_download_batch_ready(self, batch: list[Any]) -> None:
        """批量更新下载结果到表格。"""
        for idx, status in batch:
            self.update_download_row(idx, status)

    def on_download_finished(self, to_download: list, too_new_set: set, total: int, download_list: Any = None) -> None:
        """下载完成：统计成功/失败/过新数量 → 通知 → 汇总弹窗。"""
        # 统计各项计数
        too_new_count = len(too_new_set)
        success_count = 0
        failed_details: list[str] = []
        for orig_idx, p in to_download:
            if orig_idx in too_new_set:
                continue
            row = self._find_row_by_seq(orig_idx + 1)
            if row < 0:
                continue
            item = self._work_table.item(row, 1)
            status = item.text() if item else ""
            if status == "已下载":
                success_count += 1
            else:
                fname = os.path.basename(
                    getattr(p, "source_path", "") or getattr(p, "raw_filename", "") or p.get_full_number()
                )
                failed_details.append(f"  • {fname} — {status or '下载失败'}")
        failed_count = total - success_count - too_new_count

        self._status_cb(f"下载完成: {success_count}/{total} 成功")
        self._project_mark_dirty()
        self._register_task("下载", total, success_count, failed_count + too_new_count)

        # 发送本地通知（按成功/失败比例选择不同通知类型）
        from ....platform.notify import NotifyService

        if success_count > 0 and failed_count == 0:
            NotifyService.get().show(
                _("download_results_title"),
                _("download_toast_all_success").format(count=success_count),
            )
        elif success_count > 0:
            NotifyService.get().show_warning(
                _("download_results_title"),
                _("download_toast_partial").format(success=success_count, failed=failed_count),
            )
        else:
            NotifyService.get().show_warning(
                _("download_toast_failed_title"), _("download_toast_all_failed").format(total=total)
            )

        if not self._suppress_dialogs():
            lines = [
                _("download_summary_total").format(total=total),
                _("download_summary_success").format(count=success_count),
                _("download_summary_failed").format(count=failed_count),
            ]
            if too_new_count > 0:
                lines.append(_("download_summary_too_new").format(count=too_new_count))
            if failed_details:
                lines.append("")
                lines.append(_("download_summary_failed_detail"))
                shown = failed_details[:15]
                lines.extend(shown)
                if len(failed_details) > 15:
                    lines.append(f"  ... {len(failed_details) - 15} more")
            suffix = _("download_summary_all_failed_hint") if success_count == 0 and failed_count > 0 else ""
            self._show_stage_dialog(
                _("download_results_title"),
                "\n".join(lines) + suffix,
                next_action=None,
                next_label="",
            )

    def on_download_error(self, msg: str) -> None:
        """下载错误回调。"""
        self._status_cb(f"下载失败: {msg}")
        logger.error(msg)
        from ....platform.notify import NotifyService

        NotifyService.get().show("下载异常", f"download: {msg}", duration=5000)

    # ── 事件发布 ─────────────────────────────────────────────

    @staticmethod
    def _publish_event(event_name: str, data: Any) -> None:
        """封装事件发布。"""
        EventBus.instance().publish(event_name, data)
