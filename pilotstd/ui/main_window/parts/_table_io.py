"""表格数据导入导出 — 从 _table_ops.py 提取。"""

from __future__ import annotations

import csv
from typing import Any

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ....i18n import _
from ...table_constants import WORK_COLUMN_KEYS, WORK_COLUMNS


def _get_visible_cols(self) -> list[str]:
    """返回当前所有可见列的显示名称列表。"""
    return [_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS)) if not self.work_table.isColumnHidden(c)]


def _on_save_result(self, fmt: str) -> None:
    """将工作区表格保存为 txt 或 csv 文件。"""
    if self.work_table.rowCount() == 0:
        QMessageBox.information(self, _("title_hint"), _("no_data_to_save"))
        return
    vis_names = self._get_visible_cols()
    # 检查是否有隐藏列，提示用户可能丢失数据
    hidden = [_(WORK_COLUMN_KEYS[c]) for c in range(4, len(WORK_COLUMNS)) if self.work_table.isColumnHidden(c)]
    if hidden:
        msg = _("msg_export_hidden_warning").format(
            hidden_count=len(hidden), hidden_list=", ".join(hidden), visible_count=len(vis_names)
        )
        reply = QMessageBox.question(
            self, _("title_export_hint"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
    ext_map = {"txt": "TXT (*.txt)", "csv": "CSV (*.csv)"}
    path, __ = QFileDialog.getSaveFileName(None, _("dialog_save_sheet"), f"results.{fmt}", ext_map.get(fmt, "All (*)"))
    if not path:
        return
    rows = self._table_to_list()
    # 仅导出当前可见列的数据，隐藏列不导出
    visible_data_keys = [WORK_COLUMNS[c] for c in range(len(WORK_COLUMNS)) if not self.work_table.isColumnHidden(c)]
    try:
        if fmt == "txt":
            self._save_txt(path, rows, vis_names, visible_data_keys)
        elif fmt == "csv":
            self._save_csv(path, rows, vis_names, visible_data_keys)
    except OSError as e:
        QMessageBox.warning(self, _("title_save_failed"), str(e))


def _save_txt(
    self, path: str, rows: list[dict[str, Any]], cols: list[str] | None = None, data_keys: list[str] | None = None
) -> None:
    """将表格行数据保存为制表符分隔的文本文件。"""
    if cols is None:
        cols = [_(k) for k in WORK_COLUMN_KEYS]
        data_keys = list(WORK_COLUMNS)
    elif data_keys is None:
        data_keys = cols
    # 计算每列最大宽度以实现对齐输出
    widths = [len(c) for c in cols]
    for row in rows:
        for i, k in enumerate(data_keys):
            widths[i] = max(widths[i], len(self._row_get(row, k)))
    with open(path, "w", encoding="utf-8") as f:
        header = "\t".join(c.ljust(widths[i]) for i, c in enumerate(cols))
        f.write(header + "\n")
        for row in rows:
            line = "\t".join(self._row_get(row, k).ljust(widths[i]) for i, k in enumerate(data_keys))
            f.write(line + "\n")


def _row_get(self, row: Any, key: str, default: str = "") -> str:
    """从行对象（dict 或数据类）中安全读取字段值。"""
    # 兼容和对象两种行数据格式
    if isinstance(row, dict):
        return str(row.get(key, default))
    return str(getattr(row, key, default))


def _save_csv(
    self, path: str, rows: list[dict[str, Any]], cols: list[str] | None = None, data_keys: list[str] | None = None
) -> None:
    """将表格行数据保存为 UTF-8 BOM CSV 文件。"""
    if cols is None:
        cols = [_(k) for k in WORK_COLUMN_KEYS]
        data_keys = list(WORK_COLUMNS)
    elif data_keys is None:
        data_keys = cols
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in rows:
            w.writerow([self._row_get(row, k) for k in data_keys])


def _table_to_list(self) -> list[Any]:
    """将工作区表格全部行数据导出为字典列表。"""
    rows = []
    for r in range(self.work_table.rowCount()):
        row_data = {}
        for c in range(self.work_table.columnCount()):
            item = self.work_table.item(r, c)
            row_data[WORK_COLUMNS[c]] = item.text() if item else ""
        rows.append(row_data)
    return rows
