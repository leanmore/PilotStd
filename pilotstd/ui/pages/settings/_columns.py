# pilotstd/ui/pages/settings/_columns.py
# 列可见性设置 Tab 构建 mixin

from typing import Any

from PyQt6.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QVBoxLayout, QWidget

from ....i18n import _


class _ColumnsTab:
    """工作表列可见性设置。"""

    def _build_columns_page(self) -> None:
        from ...table_mixin import TOGGLEABLE_COLS, WORK_COLUMN_KEYS

        w = QWidget()
        layout = QVBoxLayout(w)
        col_gb = QGroupBox(_("columns_group"))
        col_layout = QGridLayout()
        self._col_checkboxes: dict[int, Any] = {}
        for i, c in enumerate(TOGGLEABLE_COLS):
            cb = QCheckBox(_(WORK_COLUMN_KEYS[c]))
            col_layout.addWidget(cb, i // 3, i % 3)
            self._col_checkboxes[c] = cb
        col_gb.setLayout(col_layout)
        layout.addWidget(col_gb)
        layout.addStretch()
        self._add_page(_("columns_group"), w)
