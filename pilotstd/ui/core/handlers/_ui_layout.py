# pilotstd/ui/core/handlers/_ui_layout.py
# 中央区域布局构建混入 — 从 _ui_setup.py 提取

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTextEdit,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _
from ...table_constants import WORK_COLUMN_KEYS, WORK_COLUMNS


class _UISetupLayoutMixin:
    """中央区域布局构建方法集合。"""

    def setup_file_tree(self, window: Any) -> tuple[Any, Any]:
        """创建左侧文件浏览树。返回 (left_widget, file_tree)。"""
        file_tree = QTreeWidget()
        file_tree.setHeaderLabel(_("file_nav"))
        file_tree.setColumnCount(1)
        file_tree.setAnimated(False)
        file_tree.itemExpanded.connect(window._on_tree_item_expanded)
        file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        file_tree.customContextMenuRequested.connect(window._on_file_tree_context_menu)
        window._populate_quick_access()

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(file_tree)
        return left_widget, file_tree

    def setup_work_table(self, window: Any) -> tuple[Any, Any]:
        """创建工作表，返回 (work_table, col_specs)。"""
        work_table = QTableWidget()
        work_table.setColumnCount(len(WORK_COLUMNS))
        work_table.setHorizontalHeaderLabels([_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS))])
        header = work_table.horizontalHeader()
        for c in range(len(WORK_COLUMNS)):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        # 列宽规格：(默认宽度, 最小宽度)，用于自适应布局与列宽强制约束
        col_specs: dict[int, tuple[int, int]] = {
            0: (34, 34),
            1: (54, 54),
            2: (93, 93),
            3: (241, 241),
            4: (54, 54),
            5: (93, 93),
            6: (60, 60),
            7: (60, 60),
            8: (65, 65),
            9: (34, 34),
        }
        work_table.horizontalHeader().setMinimumSectionSize(30)
        for c, (w, mn) in col_specs.items():
            work_table.setColumnWidth(c, w)
        header.sectionResized.connect(window._enforce_min_column_width)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(window._on_header_context_menu)
        window._load_column_visibility()
        window._restore_column_widths()
        window._restore_sort_state()

        work_table.setAlternatingRowColors(True)
        work_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        work_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        work_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        work_table.setSortingEnabled(True)
        work_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # 键鼠事件委托给 MainWindow 的独立函数处理
        work_table.customContextMenuRequested.connect(window._on_work_table_context_menu)
        work_table.keyPressEvent = window._table_key_press_event
        return work_table, col_specs

    def setup_log_panel(self, window: Any, right_splitter: Any) -> tuple[Any, Any]:
        """创建日志面板，返回 (log_view, progress_bar)。"""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 10, 0)

        # 日志标题行：标签 + 进度条
        log_header = QHBoxLayout()
        log_label = QLabel(_("work_log"))
        log_label.setStyleSheet("font-weight: bold; padding: 2px 4px;")
        log_header.addWidget(log_label)

        progress_bar = QProgressBar()
        progress_bar.setFormat("%p%")
        progress_bar.setTextVisible(True)
        progress_bar.setValue(0)
        log_header.addWidget(progress_bar, 1)
        log_layout.addLayout(log_header)

        log_view = QTextEdit()
        log_view.setReadOnly(True)
        log_view.setPlaceholderText(_("log_placeholder"))
        log_layout.addWidget(log_view)
        right_splitter.addWidget(log_widget)
        return log_view, progress_bar

    def setup_central(
        self,
        window: Any,
        left_widget: Any,
        work_table: Any,
        log_view: Any,
        progress_bar: Any,
        right_splitter: Any,
    ) -> Any:
        """组装中央区域，返回 main_splitter。"""
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        right_splitter.addWidget(work_table)
        # 日志面板初始占比约 28%，工作区占 72%
        right_splitter.setSizes([500, 200])
        window._restore_splitter_sizes()

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([200, 700])
        window.setCentralWidget(main_splitter)
        return main_splitter

    def setup_status_bar(self, window: Any) -> Any:
        """创建状态栏。"""
        status_bar = QStatusBar()
        status_bar.setStyleSheet("font-size: 10pt; color: #dcdcdc;")
        status_bar.showMessage(_("ready"))
        window.setStatusBar(status_bar)
        return status_bar
