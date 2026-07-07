# pilotstd/ui/controllers/query/pending.py
# 待确认管理 — 从 query_mixin.py 拆分

import csv
import logging
import os
import sys
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ....i18n import _
from ....models import ParsedStdInfo
from ...pending_query_dialog import PendingQueryDialog
from ...workers import RowUpdate

logger = logging.getLogger(__name__)


class QueryPendingMethods:
    """待确认管理方法（对话框+CSV+DB）。"""

    def _build_pending_table(self, pending_items: list[Any]) -> QTableWidget:
        """构建待确认清单表格：8 列，填充数据，调整列宽。"""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
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
        table.setRowCount(len(pending_items))
        from ....query.search_strategy import CONFIDENCE_SCORE

        for row, parsed in enumerate(pending_items):
            fn = getattr(parsed, "found_number", "") or ""
            site = getattr(parsed, "found_source_site", "") or ""
            actual_score = CONFIDENCE_SCORE.get(parsed.match_status, -1)
            score = str(actual_score) if actual_score >= 0 else "<=80"
            items = [
                parsed.get_full_number(),
                parsed.std_name or "（文件名无名称）",
                parsed.found_name or "（未找到）",
                str(parsed.year),
                fn,
                parsed.effect_status,
                str(score),
                site,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, col, item)
        table.resizeColumnsToContents()
        return table

    def _save_pending_csv(self, table: QTableWidget, save_status: QLabel) -> None:
        """导出待确认表格为 CSV 文件，结果反映在 save_status 标签。"""
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
        path = os.path.join(save_dir, f"pending_standards_{ts}.csv")
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
                for r in range(table.rowCount()):
                    row_data: list[str] = []
                    for c in range(8):
                        item = table.item(r, c)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            save_status.setText(f"已保存: pending_standards_{ts}.csv")
            save_status.setStyleSheet("color: #2a7d2a; font-size: 9pt;")
        except OSError as e:
            save_status.setText(f"保存失败: {e}")
            save_status.setStyleSheet("color: #e74c3c; font-size: 9pt;")

    def _show_pending_dialog(self: Any, pending_items: list[Any]) -> bool:
        """显示待确认清单对话框。返回 True=用户确认丢弃，False=取消。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(_("title_pending_confirm"))
        dlg.setMinimumSize(800, 400)
        layout = QVBoxLayout(dlg)

        info = QLabel(_("msg_pending_info").format(count=len(pending_items)))
        info.setWordWrap(True)
        layout.addWidget(info)

        table = self._build_pending_table(pending_items)
        layout.addWidget(table)

        save_status = QLabel("")
        save_status.setStyleSheet("color: #2a7d2a; font-size: 9pt;")

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("btn_save_csv"))
        discard_btn = QPushButton(_("btn_discard_pending"))
        cancel_btn = QPushButton(_("btn_cancel"))
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(save_status)
        btn_layout.addStretch()
        btn_layout.addWidget(discard_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        confirmed = False

        def on_save() -> None:
            nonlocal confirmed
            self._save_pending_csv(table, save_status)
            confirmed = True
            dlg.accept()

        save_btn.clicked.connect(on_save)

        def on_discard() -> None:
            nonlocal confirmed
            confirmed = True
            dlg.accept()

        discard_btn.clicked.connect(on_discard)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec()
        return confirmed

    def _on_pending_query(self: Any) -> None:
        """待确认二次查询：导入 CSV，选择站点，执行独立查询。"""
        try:
            self._do_pending_query()
        except Exception as e:
            logger.exception("待确认查询异常")
            QMessageBox.critical(None, _("title_error"), _("error_pending_query_failed").format(error=e))

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

    def _do_pending_query(self: Any) -> None:
        if not self._mgr_ready:
            return
        if self._parsed_results:
            QMessageBox.warning(None, _("title_hint"), _("workspace_not_empty"))
            return

        path, __ = QFileDialog.getOpenFileName(self, _("dialog_import_pending"), "", _("file_filter_csv"))
        if not path:
            return

        parsed_list: list[ParsedStdInfo] = []
        failed_names: list[str] = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            QMessageBox.warning(None, _("title_hint"), _("csv_empty"))
            return
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

        if not parsed_list:
            QMessageBox.warning(None, _("title_hint"), _("csv_no_standards"))
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
                RowUpdate(seq=i + 1, parsed=parsed, work_status="已查询", total=len(self._parsed_results))
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
        QMessageBox.information(None, _("pending_lookup_title"), msg)
