# pilotstd/ui/controllers/download_mixin.py
# 下载相关方法的混入类

import os
import logging
from datetime import datetime, timedelta
from PyQt6.QtWidgets import QMessageBox, QFileDialog

from ...organizer.industry_lookup import get_folder_name
from ...i18n import _
from ..workers import RowUpdate, DownloadWorker

logger = logging.getLogger(__name__)


class DownloadMixin:
    """下载相关方法，混入 MainWindow。"""

    def _on_download(self):
        """下载处理：从 Manager 的 download_list 取数据，不依赖工作表筛选。"""
        if not self._mgr_ready:
            return
        self._current_task = "download"
        download_list = self._mgr.get_stage_queue("download")
        if not download_list:
            choice = self._stage_prereq_dialog(
                _("title_hint"),
                _("msg_download_prereq"),
                _("task_query"))
            if choice == "run_prereq":
                self._on_query()
                return
            if choice == "cancel":
                return
            # choice == "skip": 强制执行（尝试从队列取，即使为空也继续）

        # 切换到下载队列视图
        self._switch_to_stage("download")
        to_download = [(i, p) for i, p in enumerate(download_list)]

        total = len(to_download)

        # 收集发布不满20个工作日的标准
        too_new_set = set()
        too_new_list = []
        for orig_idx, p in to_download:
            if self._is_too_new(p):
                too_new_list.append((orig_idx, p))
                too_new_set.add(orig_idx)
                self._enqueue_download_wait(p)
        if too_new_list and not self._suppress_dialogs:
            lines = [_("msg_new_std_too_new"), ""]
            for idx, p in too_new_list[:10]:
                num = getattr(p, 'found_number', None) or p.get_full_number()
                lines.append(f"  {num}")
            if len(too_new_list) > 10:
                lines.append(f"  ... {len(too_new_list)} total")
            QMessageBox.information(self, _("title_new_std_unavailable"), "\n".join(lines))

        self.status_changed.emit("下载中...")
        self.btn_query.setEnabled(False)
        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_changed.emit(0)

        self._clear_table()
        for i, parsed in enumerate(download_list):
            self._add_table_row(RowUpdate(seq=i + 1, parsed=parsed, work_status="待下载",
                                          total=total))

        self._download_worker = DownloadWorker(self._mgr, download_list,
                                                pause_event=self._pause_event, parent=self)
        self._download_worker.progress.connect(self.progress_changed.emit)
        self._download_worker.batch_ready.connect(self._on_download_batch_ready)

        def on_dl_finished():
            self.btn_query.setEnabled(True)
            self.btn_download.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            too_new_count = len(too_new_set)
            success_count = 0
            for r in range(self.work_table.rowCount()):
                item = self.work_table.item(r, 1)
                if item and item.text() == "已下载":
                    success_count += 1
            failed_count = total - success_count - too_new_count
            self.status_changed.emit(f"下载完成: {success_count}/{total} 成功")
            self._project.mark_dirty()
            self._register_task("下载", total, success_count, failed_count + too_new_count)

            from ...core.notify import NotifyService
            if success_count > 0 and failed_count == 0:
                NotifyService.get().show(
                    _("download_results_title"), _("download_toast_all_success").format(count=success_count))
            elif success_count > 0:
                NotifyService.get().show_warning(
                    _("download_results_title"), _("download_toast_partial").format(success=success_count, failed=failed_count))
            else:
                NotifyService.get().show_warning(
                    _("download_toast_failed_title"), _("download_toast_all_failed").format(total=total))
            # 收集下载失败的文件详情
            failed_details = []
            for orig_idx, p in to_download:
                if orig_idx in too_new_set:
                    continue
                row = self._find_row_by_seq(orig_idx + 1)
                if row >= 0:
                    item = self.work_table.item(row, 1)
                    status = item.text() if item else ""
                    if status != "已下载":
                        fname = os.path.basename(getattr(p, 'source_path', '') or getattr(p, 'raw_filename', '') or p.get_full_number())
                        failed_details.append(f"  • {fname} — {status or '下载失败'}")
            if not self._suppress_dialogs:
                has_any_success = success_count > 0
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
                suffix = _("download_summary_all_failed_hint") if not has_any_success and failed_count > 0 else ""
                self._show_stage_dialog(_("download_results_title"),
                    "\n".join(lines) + suffix,
                    next_action=self._on_normalize if has_any_success else None,
                    next_label=_("next_step_normalize") if has_any_success else "")
            self._current_task = None

        def on_dl_error(msg):
            self.btn_query.setEnabled(True)
            self.btn_download.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.status_changed.emit(f"下载失败: {msg}")
            logger.error(msg)

        self._download_worker.finished_signal.connect(on_dl_finished)
        self._download_worker.error.connect(on_dl_error)
        self._download_worker.start()

    def _on_import_download(self):
        """从文件导入标准号列表并直接下载。"""
        if not self._mgr_ready:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, _("dialog_select_file"), "",
            _("file_filter_txt") + ";;" + _("file_filter_csv") + ";;" + _("file_filter_std"))
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except OSError as e:
            QMessageBox.warning(self, _("title_import_failed"), str(e))
            return

        if not lines:
            QMessageBox.information(self, _("title_hint"), _("csv_empty"))
            return

        # 直接调 download_by_numbers 下载
        self.status_changed.emit("下载中...")
        self.btn_download.setEnabled(False)
        tasks, stats = self._mgr.download_by_numbers(lines)
        self.btn_download.setEnabled(True)

        msg = _("download_results_total") + ": " + str(stats.total) + "\n"
        msg += _("download_results_success") + ": " + str(stats.success) + "\n"
        msg += _("download_results_failed") + ": " + str(stats.failed)
        QMessageBox.information(self, _("download_results_title"), msg)
        self._project.mark_dirty()

    def _is_too_new(self, parsed) -> bool:
        """发布不满 20 个工作日（≈28 日历日），暂不可下载。"""
        pub_str = getattr(parsed, 'found_publish_date', '')
        if not pub_str:
            return False
        try:
            pub_dt = datetime.strptime(pub_str, "%Y-%m-%d")
            return pub_dt > datetime.now() - timedelta(days=28)
        except ValueError:
            return False

    def _enqueue_download_wait(self, parsed) -> None:
        """将未到下载期的标准写入下载等待队列（委托 manager）。"""
        self._mgr.enqueue_download_wait(parsed)

    def _check_download_queue(self) -> None:
        """启动时检查下载等待队列，通知用户到期项（委托 manager）。"""
        if not self._mgr_ready:
            return
        due = self._mgr.get_due_downloads()
        if not due:
            return
        nums = [d['standard_number'] for d in due[:5]]
        msg = _("download_queue_ready").format(len(due)) + "\n" + "\n".join(nums)
        if len(due) > 5:
            msg += f"\n... 等共 {len(due)} 条"
        msg += "\n" + _("download_queue_confirm")
        reply = QMessageBox.question(self, _("download_queue_title"), msg)
        if reply == QMessageBox.StandardButton.Yes:
            for d in due:
                self._mgr.remove_download_queue(d['standard_number'])
            self._on_download()

    def _update_download_row(self, idx: int, status: str):
        row = self._find_row_by_seq(idx + 1)
        if row < 0:
            return
        item = self.work_table.item(row, 1)
        if item:
            item.setText(status)

    def _on_download_batch_ready(self, batch: list):
        """批量更新下载结果，一次刷新多行。"""
        for idx, status in batch:
            self._update_download_row(idx, status)
