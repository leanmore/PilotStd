# pilotstd/ui/controllers/query/summary.py
# 查询结果摘要展示 — 从 query_mixin.py 拆分

import csv
import os
import sys
from typing import Any

from PyQt6.QtWidgets import QMessageBox

from ....i18n import _
from ....platform.notify import NotifyService
from ...pending_query_dialog import PendingQueryDialog
from ...workers import RowUpdate


class QuerySummaryMethods:
    """查询完成后的摘要统计 + 通知 + 对话框。"""

    def _count_query_actions(self) -> dict[str, int]:
        """统计各 next_action 的数量。"""
        counts: dict[str, int] = {}
        for action in ("archive", "normalize", "expire", "download", "manual_download", "not_found", "pending"):
            counts[action] = sum(1 for p in self._parsed_results if p.next_action == action)
        return counts

    def _build_query_summary_text(self, counts: dict[str, int]) -> str:
        """构建查询结果汇总文本，含分类统计 + 前15条明细文件名。"""
        lines = [_("query_results_total").format(len(self._parsed_results))]
        if counts["archive"] > 0:
            lines.append(_("query_summary_archive").format(count=counts["archive"]))
        if counts["normalize"] > 0:
            lines.append(_("query_summary_normalize").format(count=counts["normalize"]))
        if counts["expire"] > 0:
            lines.append(_("query_summary_expire").format(count=counts["expire"], extra=""))
        if counts["pending"] > 0:
            lines.append(_("query_summary_pending").format(count=counts["pending"]))
        if counts["download"] > 0:
            lines.append(_("query_summary_download").format(count=counts["download"]))
        if counts["manual_download"] > 0:
            lines.append(_("query_summary_manual_download").format(count=counts["manual_download"]))
        if counts["not_found"] > 0:
            lines.append(_("query_summary_not_found").format(count=counts["not_found"]))

        cat_keys = {
            "archive": "query_cat_archive",
            "normalize": "query_cat_normalize",
            "expire": "query_cat_expire",
            "download": "query_cat_download",
            "manual_download": "query_cat_manual_download",
            "pending": "query_cat_pending",
            "not_found": "query_cat_not_found",
        }
        detail_section = []
        for cat_action in ["archive", "normalize", "expire", "download", "manual_download", "pending", "not_found"]:
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

        return "\n".join(lines)

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

        counts = self._count_query_actions()
        # 废止标准不再在查询阶段移动——改为归档阶段由 FileMover.normalize_filename 自动归入"过期作废"子目录

        self.status_changed.emit(f"查询完成: {total} 条")
        self._project.mark_dirty()
        self._register_task("查询", total, total)

        NotifyService.get().show(
            _("query_toast_title"),
            _("query_toast_msg").format(
                total=total, archive=counts["archive"], pending=counts["pending"], expire=counts["expire"]
            ),
        )

        if not self._suppress_dialogs:
            summary_text = self._build_query_summary_text(counts)
            download_count = counts.get("archive", 0) + counts.get("normalize", 0)
            pending_count = counts["pending"]
            manual_count = counts.get("manual_download", 0)
            actions = []
            if download_count > 0:

                def do_download() -> None:
                    self._switch_to_stage("download")
                    self._on_download()

                actions.append((f"开始下载({download_count}条)", do_download))
            if manual_count > 0:

                def do_save_manual() -> None:
                    self._save_manual_download_csv()

                actions.append((f"保存手动下载清单({manual_count}条)", do_save_manual))
            if pending_count > 0:

                def do_pending() -> None:
                    self._switch_to_stage("pending")
                    pending_items = [p for p in self._parsed_results if p.next_action == "pending"]
                    dlg = PendingQueryDialog(self._mgr, pending_items, self)
                    dlg.exec()

                actions.append((f"处理待确认({pending_count}条)", do_pending))
            if download_count == 0 and manual_count == 0 and pending_count == 0:
                if counts["normalize"] > 0:
                    actions.append((_("next_step_normalize"), self._on_normalize))
                elif counts["archive"] > 0:
                    actions.append((_("next_step_save"), self._on_save_to_folder))
            self._show_stage_dialog_multi(_("query_results_title"), summary_text, actions)

    def _save_manual_download_csv(self: Any) -> None:
        """保存手动下载清单为 CSV，保存后清空对应条目（遵循工作区清洁原则）。"""
        manual_items = [p for p in self._parsed_results if p.next_action == "manual_download"]
        if not manual_items:
            return
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
        path = os.path.join(save_dir, f"manual_download_{ts}.csv")
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        _("query_pending_col_std_number"),
                        _("query_pending_col_source_filename"),
                        _("query_pending_col_web_name"),
                        _("query_pending_col_local_year"),
                        _("query_pending_col_web_number"),
                        _("query_pending_col_source_site"),
                    ]
                )
                for p in manual_items:
                    writer.writerow(
                        [
                            p.get_full_number(),
                            getattr(p, "std_name", "") or "",
                            getattr(p, "found_name", "") or "",
                            str(p.year) if p.year else "",
                            getattr(p, "found_number", "") or "",
                            getattr(p, "found_source_site", "") or "",
                        ]
                    )
            count = len(manual_items)
            self._parsed_results = [p for p in self._parsed_results if p.next_action != "manual_download"]
            self.status_changed.emit(_("manual_download_saved").format(count=count, path=path))
            QMessageBox.information(
                self,
                _("title_manual_download"),
                _("msg_manual_download_saved").format(count=count),
            )
        except OSError as e:
            QMessageBox.warning(None, _("title_save_failed"), _("msg_save_csv_failed").format(error=e))
