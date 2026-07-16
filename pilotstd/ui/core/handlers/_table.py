# pilotstd/ui/core/handlers/_table.py
"""TableHandler — 工作表列可见性管理 + 导出过滤，替代 TableMixin。"""

from __future__ import annotations

import csv
import logging
from typing import Any, Callable, Optional

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox, QTableWidget, QWidget

from ....i18n import _
from ...table_constants import TOGGLEABLE_COLS, WORK_COLUMN_KEYS, WORK_COLUMNS
from .table_flow_engine import TableFlowEngine

logger = logging.getLogger(__name__)


class TableHandler:
    """工作表列可见性管理 + 导出过滤。

    通过依赖注入替代多重继承，work_table/col_specs 作为方法参数传入，
    Handler 不持有控件引用，不发射 Qt 信号，通过 _status 回调与上层通信。
    """

    def __init__(
        self,
        config: Any,  # ConfigManager
        status_callback: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._status = status_callback
        self._parent = parent
        self._engine = TableFlowEngine()

    # ── 列可见性 ─────────────────────────────────────────

    def get_column_visibility(self, work_table: QTableWidget) -> list[bool]:
        """获取各列当前可见性（True=可见）。"""
        return [not work_table.isColumnHidden(c) for c in range(work_table.columnCount())]

    def apply_column_visibility(
        self,
        work_table: QTableWidget,
        visible: list[bool],
        col_specs: dict[int, tuple[int, int]],
    ) -> None:
        """应用列可见性设置：前四列固定显示，后续列按 visible 切换。"""
        header = work_table.horizontalHeader()
        for c in range(len(visible)):
            if c < 4:  # 前四列固定显示
                work_table.setColumnHidden(c, False)
            else:
                hidden = not visible[c] if c < len(visible) else False
                work_table.setColumnHidden(c, hidden)
                if hidden:
                    header.resizeSection(c, 0)
                elif c in col_specs:
                    header.resizeSection(c, col_specs[c][0])

    def save_column_visibility(self, work_table: QTableWidget) -> None:
        """将当前列可见性保存到配置。"""
        self._config.set("appearance.column_visibility", self.get_column_visibility(work_table))

    def load_column_visibility(
        self,
        work_table: QTableWidget,
        col_specs: dict[int, tuple[int, int]],
    ) -> None:
        """从配置恢复列可见性。"""
        default = [True] * len(WORK_COLUMNS)
        raw = self._config.get("appearance.column_visibility", default)
        visible = self._engine.validate_column_visibility(raw, len(WORK_COLUMNS), default)
        self.apply_column_visibility(work_table, visible, col_specs)

    def on_header_context_menu(
        self,
        work_table: QTableWidget,
        pos: QPoint,
        col_specs: dict[int, tuple[int, int]],
    ) -> None:
        """表头右键菜单：切换可切换列的可见性。"""
        header = work_table.horizontalHeader()
        menu = QMenu(work_table)
        for c in TOGGLEABLE_COLS:
            action = menu.addAction(_(WORK_COLUMN_KEYS[c]))
            action.setCheckable(True)
            action.setChecked(not work_table.isColumnHidden(c))
            action.setData(c)
        chosen = menu.exec(header.viewport().mapToGlobal(pos))
        menu.deleteLater()
        if chosen:
            c = chosen.data()
            hidden = not work_table.isColumnHidden(c)
            work_table.setColumnHidden(c, hidden)
            if hidden:
                header.resizeSection(c, 0)
            elif c in col_specs:
                header.resizeSection(c, col_specs[c][0])
            self.save_column_visibility(work_table)

    def get_visible_cols(self, work_table: QTableWidget) -> list[str]:
        """返回可见列的翻译后显示名（用于导出文件表头和UI提示）。"""
        return [_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS)) if not work_table.isColumnHidden(c)]

    # ── 导出 ─────────────────────────────────────────────

    def on_save_result(
        self,
        work_table: QTableWidget,
        fmt: str,
        get_rows_callback: Callable[[], list[dict]],
    ) -> None:
        """导出主入口：选择格式（txt/csv）并执行导出。"""
        if work_table.rowCount() == 0:
            QMessageBox.information(self._parent, _("title_hint"), _("no_data_to_save"))
            return

        vis_names = self.get_visible_cols(work_table)
        hidden = [_(WORK_COLUMN_KEYS[c]) for c in range(4, len(WORK_COLUMNS)) if work_table.isColumnHidden(c)]
        if hidden:
            msg = _("msg_export_hidden_warning").format(
                hidden_count=len(hidden),
                hidden_list=", ".join(hidden),
                visible_count=len(vis_names),
            )
            reply = QMessageBox.question(
                self._parent,
                _("title_export_hint"),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            reply.button(QMessageBox.StandardButton.Yes).setText(_("btn_yes"))
            reply.button(QMessageBox.StandardButton.No).setText(_("btn_no"))
            if reply != QMessageBox.StandardButton.Yes:
                return

        ext_map = {"txt": "TXT (*.txt)", "csv": "CSV (*.csv)"}
        path, __ = QFileDialog.getSaveFileName(
            None, _("dialog_save_sheet"), f"results.{fmt}", ext_map.get(fmt, "All (*)")
        )
        if not path:
            return

        rows = get_rows_callback()
        # 计算可见列的数据键名（用于行数据查找）
        visible_data_keys = [WORK_COLUMNS[c] for c in range(len(WORK_COLUMNS)) if not work_table.isColumnHidden(c)]
        try:
            if fmt == "txt":
                self.save_txt(path, rows, vis_names, visible_data_keys)
            elif fmt == "csv":
                self.save_csv(path, rows, vis_names, visible_data_keys)
        except OSError as e:
            QMessageBox.warning(self._parent, _("title_save_failed"), str(e))

    def save_txt(
        self,
        path: str,
        rows: list[dict[str, Any]],
        cols: list[str] | None = None,
        data_keys: list[str] | None = None,
    ) -> None:
        """保存TXT文件。cols为显示列名（表头），data_keys为数据键名（行查找）。"""
        if cols is None:
            cols = [_(k) for k in WORK_COLUMN_KEYS]
            data_keys = list(WORK_COLUMNS)
        elif data_keys is None:
            # 兼容旧调用：cols 同时用于表头和数据查找
            data_keys = cols
        widths = [len(c) for c in cols]
        for row in rows:
            for i, k in enumerate(data_keys):
                widths[i] = max(widths[i], len(self.row_get(row, k)))
        with open(path, "w", encoding="utf-8") as f:
            header = "\t".join(c.ljust(widths[i]) for i, c in enumerate(cols))
            f.write(header + "\n")
            for row in rows:
                line = self._engine.format_txt_row(row, data_keys)
                # 对齐：根据计算出的列宽填充
                vals = line.split("\t")
                padded = "\t".join(v.ljust(widths[i]) for i, v in enumerate(vals))
                f.write(padded + "\n")

    def save_csv(
        self,
        path: str,
        rows: list[dict[str, Any]],
        cols: list[str] | None = None,
        data_keys: list[str] | None = None,
    ) -> None:
        """保存CSV文件。cols为显示列名（表头），data_keys为数据键名（行查找）。"""
        if cols is None:
            cols = [_(k) for k in WORK_COLUMN_KEYS]
            data_keys = list(WORK_COLUMNS)
        elif data_keys is None:
            # 兼容旧调用：cols 同时用于表头和数据查找
            data_keys = cols
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            # 先写翻译后的表头，再写数据行（数据行仍使用 WORK_COLUMNS 键名）
            w = csv.writer(f)
            w.writerow(cols)
            for row in rows:
                w.writerow(self._engine.format_csv_row(row, data_keys))

    def row_get(self, row: Any, key: str, default: str = "") -> str:
        """安全获取字段值 — 兼容 dict 和 ParsedStdInfo 对象。委托 Engine。"""
        return self._engine.row_get(row, key, default)
