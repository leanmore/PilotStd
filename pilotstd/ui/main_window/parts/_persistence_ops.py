"""Extracted persistence and project methods for MainWindow."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QByteArray
from PyQt6.QtCore import Qt as QC

logger = logging.getLogger("pilotstd.ui")


def _restore_window_geometry(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_window_geometry(self)
    else:
        # _core 尚未初始化，直接从配置恢复
        geo_b64 = self._config.get("appearance.window_geometry", "")
        if geo_b64:
            self.restoreGeometry(QByteArray.fromBase64(geo_b64.encode()))


def _save_window_geometry(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_window_geometry(self)
    else:
        geo_b64 = self.saveGeometry().toBase64().data().decode()
        self._config.set("appearance.window_geometry", geo_b64)
        self._config.save()


def _save_splitter_sizes(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_splitter_sizes(self._main_splitter, self._right_splitter)
    else:
        if hasattr(self, "_main_splitter"):
            self._config.set("appearance.main_splitter", self._main_splitter.sizes())
        if hasattr(self, "_right_splitter"):
            self._config.set("appearance.right_splitter", self._right_splitter.sizes())
        self._config.save()


def _restore_splitter_sizes(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_splitter_sizes(self._main_splitter, self._right_splitter)
    else:
        sizes = self._config.get("appearance.main_splitter")
        if sizes and hasattr(self, "_main_splitter"):
            self._main_splitter.setSizes(sizes)
        sizes = self._config.get("appearance.right_splitter")
        if sizes and hasattr(self, "_right_splitter"):
            self._right_splitter.setSizes(sizes)


def _save_sort_state(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_sort_state(self.work_table)
    else:
        header = self.work_table.horizontalHeader()
        self._config.set("appearance.sort_column", header.sortIndicatorSection())
        self._config.set("appearance.sort_order", header.sortIndicatorOrder().value)
        self._config.save()


def _restore_sort_state(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_sort_state(self.work_table)
    else:
        col = self._config.get("appearance.sort_column")
        order_val = self._config.get("appearance.sort_order")
        if col is not None and order_val is not None:
            header = self.work_table.horizontalHeader()
            header.setSortIndicator(col, QC.SortOrder(order_val))


def _save_column_widths(self) -> None:
    """代理 → PersistenceHandler。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.save_column_widths(self.work_table)
    else:
        widths = [self.work_table.columnWidth(c) for c in range(self.work_table.columnCount())]
        self._config.set("appearance.column_widths", widths)


def _restore_column_widths(self) -> None:
    """代理 → PersistenceHandler（在 _core 就绪前直接操作配置）。"""
    if hasattr(self, "_core") and self._core is not None:
        self._core.persistence.restore_column_widths(self.work_table)
    else:
        widths = self._config.get("appearance.column_widths")
        if widths and len(widths) == self.work_table.columnCount():
            for c, w in enumerate(widths):
                if w > 0:
                    self.work_table.setColumnWidth(c, w)


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
