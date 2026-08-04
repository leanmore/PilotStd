# 模块：项目//核心/处理器/_持久化脚本
"""PersistenceHandler — 窗口几何/分栏/排序列宽持久化，替代 PersistenceMixin。

纯 Qt 控件 ↔ 配置的薄包装层，序列化/反序列化逻辑委托给 PersistenceFlowEngine。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .persistence_flow_engine import PersistenceFlowEngine

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QSplitter, QTableWidget

logger = logging.getLogger(__name__)

# ── 默认值常量 ──────────────────────────────────────────────────
_DEFAULT_WINDOW_GEOMETRY: dict[str, int] = {"x": 0, "y": 0, "width": 800, "height": 600}
_DEFAULT_COLUMN_WIDTH = 100


class PersistenceHandler:
    """窗口几何、分栏尺寸、排序状态、列宽的本地持久化。

    纯配置读写，无需 UI 控件持有或信号回调。
    """

    def __init__(self, config: Any) -> None:
        self._config = config
        self._engine = PersistenceFlowEngine()

    # ── 窗口几何 ─────────────────────────────────────────────

    def save_window_geometry(self, window: QMainWindow) -> None:
        """保存窗口位置和大小到配置。"""
        g = window.geometry()
        data = self._engine.serialize_window_geometry(g.x(), g.y(), g.width(), g.height())
        self._config.set("appearance.window_geometry", data)
        self._config.save()

    def restore_window_geometry(self, window: QMainWindow) -> None:
        """从配置恢复窗口位置和大小。"""
        data = self._config.get("appearance.window_geometry", _DEFAULT_WINDOW_GEOMETRY)
        result = self._engine.deserialize_window_geometry(data, _DEFAULT_WINDOW_GEOMETRY)
        window.setGeometry(result["x"], result["y"], result["width"], result["height"])

    # ── 分栏尺寸 ─────────────────────────────────────────────

    def save_splitter_sizes(self, main_splitter: QSplitter, right_splitter: QSplitter) -> None:
        """保存主分栏和右侧分栏的尺寸。"""
        self._config.set(
            "appearance.main_splitter",
            self._engine.serialize_splitter_sizes(main_splitter.sizes()),
        )
        self._config.set(
            "appearance.right_splitter",
            self._engine.serialize_splitter_sizes(right_splitter.sizes()),
        )
        self._config.save()

    def restore_splitter_sizes(self, main_splitter: QSplitter, right_splitter: QSplitter) -> None:
        """从配置恢复主分栏和右侧分栏的尺寸。"""
        sizes = self._config.get("appearance.main_splitter")
        if main_splitter:
            main_splitter.setSizes(self._engine.deserialize_splitter_sizes(sizes, main_splitter.sizes()))
        sizes = self._config.get("appearance.right_splitter")
        if right_splitter:
            right_splitter.setSizes(self._engine.deserialize_splitter_sizes(sizes, right_splitter.sizes()))

    # ── 排序/表头状态 ────────────────────────────────────────

    def save_sort_state(self, work_table: QTableWidget) -> None:
        """保存表头完整状态（含排序列和排序方向）。"""
        header = work_table.horizontalHeader()
        state_bytes = header.saveState().data()
        data = self._engine.serialize_header_state(state_bytes)
        self._config.set("appearance.header_state", data)
        self._config.save()

    def restore_sort_state(self, work_table: QTableWidget) -> None:
        """从配置恢复表头完整状态（含排序列和排序方向）。"""
        data = self._config.get("appearance.header_state")
        if data:
            from PyQt6.QtCore import QByteArray

            state_bytes = self._engine.deserialize_header_state(data)
            if state_bytes:
                header = work_table.horizontalHeader()
                header.restoreState(QByteArray(state_bytes))

    # ── 列宽 ─────────────────────────────────────────────────

    def save_column_widths(self, work_table: QTableWidget) -> None:
        """保存各列宽度。"""
        widths = [work_table.columnWidth(c) for c in range(work_table.columnCount())]
        self._config.set(
            "appearance.column_widths",
            self._engine.serialize_column_widths(widths),
        )
        self._config.save()

    def restore_column_widths(self, work_table: QTableWidget) -> None:
        """从配置恢复各列宽度。"""
        col_count = work_table.columnCount()
        widths = self._config.get("appearance.column_widths")
        if widths is None:
            return
        result = self._engine.deserialize_column_widths(widths, col_count, _DEFAULT_COLUMN_WIDTH)
        for c, w in enumerate(result):
            if w > 0:
                work_table.setColumnWidth(c, w)
