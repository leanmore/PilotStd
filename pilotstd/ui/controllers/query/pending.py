# pilotstd/ui/controllers/query/pending.py
# 待确认管理 — 从 query_mixin.py 拆分

import csv
import logging
import re
from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
)

from ....i18n import _
from ....models import ParsedStdInfo
from ...pending_query_dialog import PendingQueryDialog
from ...workers import RowUpdate

logger = logging.getLogger(__name__)


class QueryPendingMethods:
    """待确认管理方法（对话框+CSV+DB）。"""

    def _export_pending_csv(self, save_status: QLabel | None = None) -> str | None:
        """统一导出函数：从 pending_lookup 表读取全部待确认记录写 CSV。
        不依赖界面状态，不过滤 is_valid_standard，两个入口结果一致。"""
        rows = self._mgr.get_pending_items()
        if not rows:
            if save_status is not None:
                save_status.setText(_("msg_no_pending_items"))
                save_status.setStyleSheet("color: #e74c3c; font-size: 9pt;")
            return None

        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, __ = QFileDialog.getSaveFileName(
            None,
            _("dialog_save_pending"),
            f"pending_standards_{ts}.csv",
            _("file_filter_csv"),
        )
        if not path:
            return None

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
                        _("query_pending_col_status"),
                        _("query_pending_col_confidence"),
                        _("query_pending_col_source_site"),
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

    def _on_pending_query(self: Any) -> None:
        """待确认二次查询：导入 CSV，选择站点，执行独立查询。"""
        try:
            self._do_pending_query()
        except Exception as e:
            logger.exception("待确认查询异常")
            QMessageBox.critical(self, _("title_error"), _("error_pending_query_failed").format(error=e))

    def _writeback_and_reclassify(self: Any, results: list[Any], parsed_list: list[Any]) -> None:
        """将二次查询结果回写到 parsed_list，然后重新路由分类。"""
        for idx, r in results:
            if idx < len(parsed_list) and r is not None:
                p = parsed_list[idx]
                if r.standard_name:
                    p.found_name = r.standard_name
                p.found_source_site = getattr(r, "source_site", "") or ""
                p.found_number = getattr(r, "standard_number", "") or ""
                p.effect_status = getattr(r, "status", "") or ""
                p.match_status = getattr(r, "match_status", "") or ""
        self._mgr._classifier._router.apply_actions(parsed_list)

    def _parse_pending_csv(self: Any, path: str) -> tuple[list[ParsedStdInfo], list[str]]:
        """解析待确认 CSV 文件，返回 (parsed_list, failed_names)。"""
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

    def _do_pending_query(self: Any) -> None:
        if not self._mgr_ready:
            return
        if self._parsed_results:
            QMessageBox.warning(self, _("title_hint"), _("workspace_not_empty"))
            return

        path, __ = QFileDialog.getOpenFileName(self, _("dialog_import_pending"), "", _("file_filter_csv"))
        if not path:
            return

        parsed_list, failed_names = self._parse_pending_csv(path)
        if not parsed_list:
            QMessageBox.warning(self, _("title_hint"), _("csv_no_standards"))
            return

        msg = _("msg_csv_parse_result").format(count=len(parsed_list))
        if failed_names:
            msg += f"，{_('msg_csv_unrecognized').format(count=len(failed_names))}:\n" + "\n".join(failed_names[:5])
            if len(failed_names) > 5:
                msg += f"\n... 等共 {len(failed_names)} 条"
        msg += "\n\n是否继续？"
        reply = self._question_dlg(_("title_pending_query"), msg)
        if reply != QMessageBox.StandardButton.Yes:
            self.status_changed.emit(_("status_pending_cancelled"))
            return

        dlg = PendingQueryDialog(self._mgr, parsed_list, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.status_changed.emit(_("status_pending_cancelled"))
            return

        results = dlg.get_results()
        self._writeback_and_reclassify(results, parsed_list)
        self._clear_table()
        self._parsed_results = parsed_list

        for i, parsed in enumerate(self._parsed_results):
            self._add_table_row(
                RowUpdate(
                    seq=self.work_table.rowCount() + 1,
                    parsed=parsed,
                    work_status="已查询",
                    total=len(self._parsed_results),
                )
            )

        total = len(self._parsed_results)
        found = sum(1 for p in self._parsed_results if p.found_name)
        self.status_changed.emit(f"待确认查询完成: {found}/{total}")

        QMessageBox.information(
            self,
            _("title_pending_query_complete"),
            _("msg_pending_query_complete").format(found=found, failed=total - found),
        )

    def _write_pending_to_db(self: Any, pending_items: list[Any]) -> None:
        """将待确认项写入 pending_lookup 表（委托 manager）。"""
        self._mgr.record_pending(pending_items)

    def _resolve_pending_in_db(self: Any, pending_items: list[Any], resolution: str) -> None:
        """标记待确认项为已处理（委托 manager）。"""
        self._mgr.resolve_pending(pending_items, resolution)

    def _check_pending_lookup(self: Any) -> None:
        """启动时检查待确认清单（委托 manager）。"""
        if not self._mgr_ready:
            return
        pending_rows = self._mgr.get_pending_items()
        if not pending_rows:
            return
        count = len(pending_rows)
        nums = [r["standard_number"] for r in pending_rows[:5]]
        msg = _("pending_lookup_msg").format(count) + "\n" + "\n".join(nums)
        if count > 5:
            msg += f"\n... 等共 {count} 条"
        msg += "\n" + _("pending_lookup_hint")
        QMessageBox.information(self, _("pending_lookup_title"), msg)
