# pilotstd/ui/controllers/persistence_mixin.py
# 窗口几何/分栏/排序列宽持久化 — 从 main_window.py 提取

import logging
from PyQt6.QtCore import Qt as QC

logger = logging.getLogger(__name__)


class PersistenceMixin:
    """窗口几何、分栏尺寸、排序状态、列宽的本地持久化。
    依赖 self._config, self.work_table, self._main_splitter, self._right_splitter。
    """

    # ── 窗口几何 ─────────────────────────────────────────

    def _restore_window_geometry(self):
        geo_b64 = self._config.get("ui.window_geometry", "")
        if geo_b64:
            from PyQt6.QtCore import QByteArray
            ok = self.restoreGeometry(QByteArray.fromBase64(geo_b64.encode()))
            if ok:
                logger.debug("已恢复窗口位置和大小")

    def _save_window_geometry(self):
        geo_b64 = self.saveGeometry().toBase64().data().decode()
        self._config.set("ui.window_geometry", geo_b64)
        self._config.save()

    # ── 分栏尺寸 ─────────────────────────────────────────

    def _save_splitter_sizes(self):
        if hasattr(self, '_main_splitter'):
            self._config.set("ui.main_splitter", self._main_splitter.sizes())
        if hasattr(self, '_right_splitter'):
            self._config.set("ui.right_splitter", self._right_splitter.sizes())
        self._config.save()

    def _restore_splitter_sizes(self):
        sizes = self._config.get("ui.main_splitter")
        if sizes and hasattr(self, '_main_splitter'):
            self._main_splitter.setSizes(sizes)
        sizes = self._config.get("ui.right_splitter")
        if sizes and hasattr(self, '_right_splitter'):
            self._right_splitter.setSizes(sizes)

    # ── 排序状态 ─────────────────────────────────────────

    def _save_sort_state(self):
        header = self.work_table.horizontalHeader()
        self._config.set("ui.sort_column", header.sortIndicatorSection())
        self._config.set("ui.sort_order", header.sortIndicatorOrder().value)
        self._config.save()

    def _restore_sort_state(self):
        col = self._config.get("ui.sort_column")
        order_val = self._config.get("ui.sort_order")
        if col is not None and order_val is not None:
            order = QC.SortOrder(order_val)
            header = self.work_table.horizontalHeader()
            header.setSortIndicator(col, order)
