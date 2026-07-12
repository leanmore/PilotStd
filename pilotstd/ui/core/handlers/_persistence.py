# pilotstd/ui/core/handlers/_persistence.py
"""PersistenceHandler — 窗口几何/分栏/排序列宽持久化，替代 PersistenceMixin。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QSplitter, QTableWidget

logger = logging.getLogger(__name__)


class PersistenceHandler:
    """窗口几何、分栏尺寸、排序状态、列宽的本地持久化。

    纯配置读写，无需 UI 控件持有或信号回调。
    """

    def __init__(self, config: Any) -> None:
        self._config = config

    # ── 窗口几何 ─────────────────────────────────────────────

    def restore_window_geometry(self, window: QMainWindow) -> None:
        """从配置恢复窗口位置和大小。"""
        geo_b64 = self._config.get("appearance.window_geometry", "")
        if geo_b64:
            from PyQt6.QtCore import QByteArray

            ok = window.restoreGeometry(QByteArray.fromBase64(geo_b64.encode()))
            if ok:
                logger.debug("已恢复窗口位置和大小")

    def save_window_geometry(self, window: QMainWindow) -> None:
        """保存窗口位置和大小到配置。"""
        geo_b64 = window.saveGeometry().toBase64().data().decode()
        self._config.set("appearance.window_geometry", geo_b64)
        self._config.save()

    # ── 分栏尺寸 ─────────────────────────────────────────────

    def save_splitter_sizes(self, main_splitter: QSplitter, right_splitter: QSplitter) -> None:
        """保存主分栏和右侧分栏的尺寸。"""
        self._config.set("appearance.main_splitter", main_splitter.sizes())
        self._config.set("appearance.right_splitter", right_splitter.sizes())
        self._config.save()

    def restore_splitter_sizes(self, main_splitter: QSplitter, right_splitter: QSplitter) -> None:
        """从配置恢复主分栏和右侧分栏的尺寸。"""
        sizes = self._config.get("appearance.main_splitter")
        if sizes and main_splitter:
            main_splitter.setSizes(sizes)
        sizes = self._config.get("appearance.right_splitter")
        if sizes and right_splitter:
            right_splitter.setSizes(sizes)

    # ── 排序状态 ─────────────────────────────────────────────

    def save_sort_state(self, work_table: QTableWidget) -> None:
        """保存排序列和排序方向。"""
        header = work_table.horizontalHeader()
        self._config.set("appearance.sort_column", header.sortIndicatorSection())
        self._config.set("appearance.sort_order", header.sortIndicatorOrder().value)
        self._config.save()

    def restore_sort_state(self, work_table: QTableWidget) -> None:
        """从配置恢复排序列和排序方向。"""
        col = self._config.get("appearance.sort_column")
        order_val = self._config.get("appearance.sort_order")
        if col is not None and order_val is not None:
            from PyQt6.QtCore import Qt as QC

            header = work_table.horizontalHeader()
            header.setSortIndicator(col, QC.SortOrder(order_val))

    # ── 列宽 ─────────────────────────────────────────────────

    def save_column_widths(self, work_table: QTableWidget) -> None:
        """保存各列宽度。"""
        widths = [work_table.columnWidth(c) for c in range(work_table.columnCount())]
        self._config.set("appearance.column_widths", widths)
        self._config.save()

    def restore_column_widths(self, work_table: QTableWidget) -> None:
        """从配置恢复各列宽度。"""
        widths = self._config.get("appearance.column_widths")
        if widths and len(widths) == work_table.columnCount():
            for c, w in enumerate(widths):
                if w > 0:
                    work_table.setColumnWidth(c, w)
