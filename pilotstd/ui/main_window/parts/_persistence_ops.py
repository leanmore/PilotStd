"""Extracted persistence and project methods for MainWindow."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QByteArray

from pilotstd.ui.core.handlers.persistence_flow_engine import PersistenceFlowEngine

logger = logging.getLogger("pilotstd.ui")

# ── 默认值常量 ──────────────────────────────────────────────────
_DEFAULT_WINDOW_GEOMETRY: dict[str, int] = {"x": 0, "y": 0, "width": 800, "height": 600}
_DEFAULT_COLUMN_WIDTH = 100
_ENGINE = PersistenceFlowEngine()


# ── 窗口几何状态持久化 ──


def _restore_window_geometry(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_window_geometry(self)
    else:
        data = self._config.get("appearance.window_geometry", _DEFAULT_WINDOW_GEOMETRY)
        result = _ENGINE.deserialize_window_geometry(data, _DEFAULT_WINDOW_GEOMETRY)
        self.setGeometry(result["x"], result["y"], result["width"], result["height"])


def _save_window_geometry(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_window_geometry(self)
    else:
        g = self.geometry()
        data = _ENGINE.serialize_window_geometry(g.x(), g.y(), g.width(), g.height())
        self._config.set("appearance.window_geometry", data)
        self._config.save()


# ── 分割器状态持久化 ──


def _save_splitter_sizes(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_splitter_sizes(self._main_splitter, self._right_splitter)
    else:
        if hasattr(self, "_main_splitter"):
            self._config.set(
                "appearance.main_splitter",
                _ENGINE.serialize_splitter_sizes(self._main_splitter.sizes()),
            )
        if hasattr(self, "_right_splitter"):
            self._config.set(
                "appearance.right_splitter",
                _ENGINE.serialize_splitter_sizes(self._right_splitter.sizes()),
            )
        self._config.save()


def _restore_splitter_sizes(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_splitter_sizes(self._main_splitter, self._right_splitter)
    else:
        sizes = self._config.get("appearance.main_splitter")
        if hasattr(self, "_main_splitter"):
            self._main_splitter.setSizes(_ENGINE.deserialize_splitter_sizes(sizes, self._main_splitter.sizes()))
        sizes = self._config.get("appearance.right_splitter")
        if hasattr(self, "_right_splitter"):
            self._right_splitter.setSizes(_ENGINE.deserialize_splitter_sizes(sizes, self._right_splitter.sizes()))


# ── 排序状态持久化 ──


def _save_sort_state(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_sort_state(self.work_table)
    else:
        header = self.work_table.horizontalHeader()
        state_bytes = header.saveState().data()
        data = _ENGINE.serialize_header_state(state_bytes)
        self._config.set("appearance.header_state", data)
        self._config.save()


def _restore_sort_state(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_sort_state(self.work_table)
    else:
        data = self._config.get("appearance.header_state")
        if data:
            state_bytes = _ENGINE.deserialize_header_state(data)
            if state_bytes:
                header = self.work_table.horizontalHeader()
                header.restoreState(QByteArray(state_bytes))


# ── 列宽持久化 ──


def _save_column_widths(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_column_widths(self.work_table)
    else:
        widths = [self.work_table.columnWidth(c) for c in range(self.work_table.columnCount())]
        self._config.set("appearance.column_widths", _ENGINE.serialize_column_widths(widths))
        self._config.save()


def _restore_column_widths(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_column_widths(self.work_table)
    else:
        col_count = self.work_table.columnCount()
        widths = self._config.get("appearance.column_widths")
        if widths is None:
            return
        result = _ENGINE.deserialize_column_widths(widths, col_count, _DEFAULT_COLUMN_WIDTH)
        for c, w in enumerate(result):
            if w > 0:
                self.work_table.setColumnWidth(c, w)


# ── 项目文件操作 ──


def _on_open_project(self) -> None:
    """代理 → ProjectHandler。"""
    if not hasattr(self, "_core") or self._core is None:
        logger.warning("_core 未就绪，跳过打开项目")
        return
    self._core.project.on_open_project()


def _on_save_query_project(self) -> None:
    """代理 → ProjectHandler。"""
    if not hasattr(self, "_core") or self._core is None:
        logger.warning("_core 未就绪，跳过保存查询项目")
        return
    self._core.project.on_save_query_project()


def _on_save_download_project(self) -> None:
    """代理 → ProjectHandler。"""
    if not hasattr(self, "_core") or self._core is None:
        logger.warning("_core 未就绪，跳过保存下载项目")
        return
    self._core.project.on_save_download_project()
