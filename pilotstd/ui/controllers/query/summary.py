# pilotstd/ui/controllers/query/summary.py
# 查询结果摘要展示 — 从 query_mixin.py 拆分

import os
from typing import Any

from ....i18n import _
from ....platform.notify import NotifyService
from ...pending_query_dialog import PendingQueryDialog
from ...workers import RowUpdate


class QuerySummaryMethods:
    """查询完成后的摘要统计 + 通知 + 对话框。"""

    def _show_query_summary(self: Any) -> None:
        total = len(self._parsed_results)

        pending = [p for p in self._parsed_results if p.next_action == "pending"]
        if pending:
            self._write_pending_to_db(pending)
        if pending and not self._suppress_dialogs:
            if self._show_pending_dialog(pending):
                self._parsed_results = [p for p in self._parsed_results if p.next_action != "pending"]
                self._resolve_pending_in_db(pending, "discarded")
                self._clear_table()
                new_total = len(self._parsed_results)
                for i, parsed in enumerate(self._parsed_results):
                    self._add_table_row(RowUpdate(seq=i + 1, parsed=parsed, work_status="已分类", total=new_total))
                total = new_total
                self.status_changed.emit(_("pending_discarded").format(len(pending), total))

        archive_count = sum(1 for p in self._parsed_results if p.next_action == "archive")
        normalize_count = sum(1 for p in self._parsed_results if p.next_action == "normalize")
        expire_count = sum(1 for p in self._parsed_results if p.next_action == "expire")
        not_found_count = sum(1 for p in self._parsed_results if p.next_action == "not_found")
        pending_count = sum(1 for p in self._parsed_results if p.next_action == "pending")

        expired_moved = 0
        if expire_count > 0:
            expired_moved = self._auto_move_expired()

        self.status_changed.emit(f"查询完成: {total} 条")
        self._project.mark_dirty()
        self._register_task("查询", total, total)

        NotifyService.get().show(
            _("query_toast_title"),
            _("query_toast_msg").format(total=total, archive=archive_count, pending=pending_count, expire=expire_count),
        )

        if not self._suppress_dialogs:
            lines = [_("query_results_total").format(total)]
            if archive_count > 0:
                lines.append(_("query_summary_archive").format(count=archive_count))
            if normalize_count > 0:
                lines.append(_("query_summary_normalize").format(count=normalize_count))
            if expire_count > 0:
                extra = f" ({_('expired_move_info').format(expired_moved)})" if expired_moved else ""
                lines.append(_("query_summary_expire").format(count=expire_count, extra=extra))
            if pending_count > 0:
                lines.append(_("query_summary_pending").format(count=pending_count))
            if not_found_count > 0:
                lines.append(_("query_summary_not_found").format(count=not_found_count))

            detail_section = []
            cat_keys = {
                "archive": "query_cat_archive",
                "normalize": "query_cat_normalize",
                "expire": "query_cat_expire",
                "pending": "query_cat_pending",
                "not_found": "query_cat_not_found",
            }
            for cat_action in ["archive", "normalize", "expire", "pending", "not_found"]:
                cat_label = _(cat_keys[cat_action])
                cat_items = [p for p in self._parsed_results if p.next_action == cat_action]
                if cat_items:
                    cat_details = []
                    for p in cat_items[:15]:
                        fname = (
                            os.path.basename(getattr(p, "source_path", "") or "")
                            or getattr(p, "raw_filename", "")
                            or p.get_full_number()
                        )
                        cat_details.append(f"    - {fname}")
                    if cat_details:
                        detail_section.append(f"  {cat_label}:")
                        detail_section.extend(cat_details)
                        if len(cat_items) > 15:
                            detail_section.append(f"    ... 还有 {len(cat_items) - 15} 个")
            if detail_section:
                lines.append("")
                lines.extend(detail_section)

            download_count = sum(1 for p in self._parsed_results if p.next_action == "download")
            actions = []
            if download_count > 0:

                def do_download() -> None:
                    self._switch_to_stage("download")
                    self._on_download()

                actions.append((f"开始下载({download_count}条)", do_download))
            if pending_count > 0:

                def do_pending() -> None:
                    self._switch_to_stage("pending")
                    pending_items = [p for p in self._parsed_results if p.next_action == "pending"]
                    dlg = PendingQueryDialog(self._mgr, pending_items, self)
                    dlg.exec()

                actions.append((f"处理待确认({pending_count}条)", do_pending))
            if download_count == 0 and pending_count == 0:
                if normalize_count > 0:
                    actions.append((_("next_step_normalize"), self._on_normalize))
                elif archive_count > 0:
                    actions.append((_("next_step_save"), self._on_save_to_folder))
            self._show_stage_dialog_multi(_("query_results_title"), "\n".join(lines), actions)

        self._current_task = None
