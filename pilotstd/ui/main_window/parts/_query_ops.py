"""Extracted query signal handling methods for MainWindow."""

from __future__ import annotations

import csv
import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox

from ....i18n import _
from ...pending_query_dialog import PendingQueryDialog
from ...workers import RowUpdate

logger = logging.getLogger("pilotstd.ui")


def _on_query_result_ready(self, idx: int, result: Any) -> None:
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


def _on_pending_query(self) -> None:
    try:
        self._do_pending_query()
    except Exception as e:
        logger.exception("待确认查询异常")
        QMessageBox.critical(self, _("title_error"), _("error_pending_query_failed").format(error=e))


def _do_pending_query(self) -> None:
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
    self._mgr._classifier.classify(
        [r for _, r in results], parsed_list, self._mgr._download_list, self._mgr._expire_list, self._mgr._pending_list
    )
    self._mgr._queried_items = parsed_list
    self._clear_table()
    print(f"[TRACE] _do_pending_query: 修改前 id={id(self._parsed_results)}")
    self._parsed_results.clear()
    self._parsed_results.extend(parsed_list)
    print(f"[TRACE] _do_pending_query: 修改后 id={id(self._parsed_results)} len={len(self._parsed_results)}")
    for i, p in enumerate(self._parsed_results):
        self._add_table_row(
            RowUpdate(
                seq=self.work_table.rowCount() + 1,
                parsed=p,
                work_status="已查询",
                total=len(self._parsed_results),
            )
        )
    total = len(self._parsed_results)
    found = sum(1 for p in self._parsed_results if p.found_name)
    self.status_changed.emit(f"待确认查询完成: {found}/{total}")
    self._show_query_summary()
    self._update_button_states()


def _parse_pending_csv(self, path: str) -> tuple[list, list[str]]:
    parsed_list: list = []
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


def _show_query_summary(self) -> None:
    """查询完成后的汇总通知（转发到 QueryUIHandler）。"""
    if hasattr(self, "_core"):
        self._core.query.show_query_summary()
