# pilotstd/ui/core/handlers/_ui_setup.py
"""UISetupHandler — UI 构建（菜单栏、工具栏、中央区域、系统托盘等），替代 UISetupMixin。"""

from __future__ import annotations

import atexit
import logging
import signal
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _
from ...table_constants import WORK_COLUMN_KEYS, WORK_COLUMNS
from ...widgets import NotificationBellWidget
from ...workers import LogHandler

logger = logging.getLogger("pilotstd.ui")


class UISetupHandler:
    """UI 构建 — 提供所有 setup_* 方法。

    通过依赖注入替代多重继承，window 作为方法参数传入以访问 MainWindow 的回调。
    """

    def __init__(
        self,
        config: Any,
        mgr: Any,
        project: Any,
        status_callback: Callable[[str], None],
        progress_callback: Callable[[int], None],
        on_auto_save: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._mgr = mgr
        self._project = project
        self._status = status_callback
        self._progress = progress_callback
        self._on_auto_save = on_auto_save
        self._parent = parent

    # ================================================================
    # 系统托盘
    # ================================================================

    def setup_tray(self, window: QWidget) -> QSystemTrayIcon:
        """系统托盘：最小化到托盘，双击恢复。返回 tray 实例供后续使用。"""
        tray = QSystemTrayIcon(window)
        tray.setIcon(window.windowIcon())
        tray.setToolTip("PilotStd")
        tray_menu = QMenu()
        tray_menu.addAction(_("tray_show"), window._restore_from_tray)
        tray_menu.addSeparator()
        tray_menu.addAction(_("exit"), window._quit_app)
        tray.setContextMenu(tray_menu)
        tray.activated.connect(window._on_tray_activated)
        tray.show()
        from ....platform.notify import NotifyService

        NotifyService.init(tray)
        return tray

    def on_tray_activated(self, reason: object, window: QWidget) -> None:
        """托盘图标激活回调。"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            window._restore_from_tray()

    # ================================================================
    # 菜单栏
    # ================================================================

    def setup_menu(self, window: QWidget, action_callbacks: dict[str, Any]) -> None:
        """构建菜单栏：文件 | 工具 | 设置 | 帮助。"""
        mb = window.menuBar()
        assert mb is not None, "menuBar() 不应为 None"

        # ── 文件 ──
        file_menu = mb.addMenu(_("file"))

        a = file_menu.addAction(_("open_file"), action_callbacks["on_open_file"])
        a.setToolTip("选择单个标准文件并导入项目")
        a = file_menu.addAction(_("open_folder"), action_callbacks["on_open_folder"])
        a.setToolTip("选择文件夹（含子文件夹）并导入项目")
        file_menu.addSeparator()

        save_result_menu = file_menu.addMenu(_("export_sheet"))
        save_result_menu.setToolTip("将工作区表格导出为文件")
        save_result_menu.addAction(_("export_txt"), action_callbacks["on_save_result_txt"])
        save_result_menu.addAction(_("export_csv"), action_callbacks["on_save_result_csv"])

        file_menu.addSeparator()
        a = file_menu.addAction(_("export_file_list"), action_callbacks["on_export_file_list"])
        a.setToolTip("将选中文件夹内所有文件名导出为列表（可选是否含完整路径）")
        a = file_menu.addAction(_("export_folder_tree"), action_callbacks["on_export_folder_tree"])
        a.setToolTip("将选中文件夹的目录树形结构导出为文本")
        file_menu.addSeparator()
        a = file_menu.addAction(_("save_query_project"), action_callbacks["on_save_query_project"])
        a.setToolTip("将当前查询列表保存为 .pilotstd 项目文件，便于下次恢复")
        a = file_menu.addAction(_("save_download_project"), action_callbacks["on_save_download_project"])
        a.setToolTip("将当前下载队列保存为 .pilotstd 项目文件，便于下次恢复")
        a = file_menu.addAction(_("import_download"), action_callbacks["on_import_download"])
        a.setToolTip("从文件导入标准号列表并直接下载，无需先查询")
        file_menu.addSeparator()
        a = file_menu.addAction(_("open_project"), action_callbacks["on_open_project"])
        a.setToolTip("从 .pilotstd 项目文件恢复之前保存的工作状态")
        file_menu.addSeparator()
        a = file_menu.addAction(_("exit"), window.close)
        a.setToolTip("退出 PilotStd（未保存的工作状态将自动保存）")

        # ── 工具 ──
        tool_menu = mb.addMenu(_("tools"))

        rule_action = tool_menu.addAction(_("query_rules"), action_callbacks["on_rule_query"])
        rule_action.setToolTip("管理查询/下载网站适配规则，支持 JSON 导入导出")

        tool_menu.addAction(_("task_center"), action_callbacks["on_task_center"])
        tool_menu.addSeparator()
        tool_menu.addAction(_("cleanup_empty_dirs"), action_callbacks["on_cleanup_empty_dirs"])
        tool_menu.addAction(_("collect_unrecognized"), action_callbacks["on_collect_unrecognized"])
        tool_menu.addSeparator()
        tool_menu.addAction(_("export_diag"), action_callbacks["on_export_diag"])
        tool_menu.addSeparator()
        tool_menu.addAction(_("pending_query"), action_callbacks["on_pending_query"])

        # ── 设置 ──
        settings_menu = mb.addMenu(_("settings"))
        settings_menu.addAction(_("preferences"), action_callbacks["on_settings"])

        # ── 帮助 ──
        help_menu = mb.addMenu(_("help"))
        help_menu.addAction(_("check_update"), action_callbacks["on_check_update"])
        help_menu.addAction(_("about"), action_callbacks["on_about"])

    # ================================================================
    # 工具栏
    # ================================================================

    def _make_toolbar_btn(self, toolbar, style, text_key, icon_sp, tooltip, callback):
        """创建单个工具栏按钮并添加到工具栏。"""
        btn = QPushButton(_(text_key))
        btn.setIcon(style.standardIcon(icon_sp))
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        toolbar.addWidget(btn)
        return btn

    def setup_toolbar(self, window: QWidget, action_callbacks: dict[str, Any]) -> dict[str, Any]:
        """构建工具栏，返回按钮字典供状态控制。"""
        toolbar = QToolBar(_("toolbar_main"))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        style = window.style()
        assert style is not None, "style() 不应为 None"
        SP = style.StandardPixmap

        btn_specs = {
            "btn_select": ("toolbar_import", SP.SP_DirOpenIcon, "导入文件夹到项目中", "on_select"),
            "btn_query": (
                "toolbar_query",
                SP.SP_FileDialogContentsView,
                "对扫描后的标准号在网站上查询有效性",
                "on_query",
            ),
            "btn_download": ("toolbar_download", SP.SP_ArrowDown, "对已有新版本的标准进行下载", "on_download"),
            "btn_normalize": (
                "toolbar_normalize",
                SP.SP_FileDialogDetailedView,
                "对扫描结果生成规范标准文件名",
                "on_normalize",
            ),
            "btn_save": ("toolbar_save", SP.SP_DriveFDIcon, "将文件以规范名称保存到设定文件夹", "on_save_to_folder"),
            "btn_auto": ("toolbar_auto", SP.SP_MediaPlay, "自动依次执行全流程", "on_auto_run"),
            "btn_announce": (
                "toolbar_announce",
                SP.SP_MessageBoxWarning,
                "抓取国家标准公告，检测本地标准变更",
                "on_check_announcements",
            ),
        }
        buttons: dict[str, Any] = {}
        for name, (text_key, icon_sp, tip, cb_key) in btn_specs.items():
            cb = action_callbacks[cb_key]
            buttons[name] = self._make_toolbar_btn(toolbar, style, text_key, icon_sp, tip, cb)

        toolbar.addSeparator()

        pause_btn = QPushButton(_("toolbar_pause"))
        pause_btn.setIcon(SP.SP_MediaPause)
        pause_btn.setToolTip("暂停/继续当前任务")
        pause_btn.clicked.connect(action_callbacks["on_pause_toggle"])
        toolbar.addWidget(pause_btn)
        pause_btn.setEnabled(False)
        buttons["btn_pause"] = pause_btn

        cancel_btn = QPushButton(_("toolbar_cancel"))
        cancel_btn.setIcon(SP.SP_DialogCancelButton)
        cancel_btn.setToolTip("取消当前任务")
        cancel_btn.clicked.connect(action_callbacks["on_cancel"])
        toolbar.addWidget(cancel_btn)
        cancel_btn.setEnabled(False)
        buttons["btn_cancel"] = cancel_btn

        notification_bell = NotificationBellWidget(window)
        toolbar.addWidget(notification_bell)
        toolbar.addSeparator()
        buttons["notification_bell"] = notification_bell

        return buttons

    # ================================================================
    # 中央区域（左右分栏）
    # ================================================================

    def setup_file_tree(self, window: QWidget) -> QWidget:
        """创建左侧文件浏览树。返回 left_widget 供布局组装。"""
        file_tree = QTreeWidget()
        file_tree.setHeaderLabel(_("file_nav"))
        file_tree.setColumnCount(1)
        file_tree.setAnimated(True)
        file_tree.itemExpanded.connect(window._on_tree_item_expanded)
        file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        file_tree.customContextMenuRequested.connect(window._on_file_tree_context_menu)
        window._populate_quick_access()

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(file_tree)
        return left_widget, file_tree

    def setup_work_table(self, window: QWidget) -> tuple[QTableWidget, dict[int, tuple[int, int]]]:
        """创建工作表，返回 (work_table, col_specs)。"""
        work_table = QTableWidget()
        work_table.setColumnCount(len(WORK_COLUMNS))
        work_table.setHorizontalHeaderLabels([_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS))])
        header = work_table.horizontalHeader()
        for c in range(len(WORK_COLUMNS)):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        col_specs: dict[int, tuple[int, int]] = {
            0: (34, 34),  # 序号
            1: (54, 54),  # 工作状态
            2: (93, 93),  # 标准编号
            3: (241, 241),  # 标准名称
            4: (54, 54),  # 生效状态
            5: (93, 93),  # 替代标准
            6: (60, 60),  # 发布日期
            7: (60, 60),  # 实施日期
            8: (65, 65),  # 发布部门
            9: (34, 34),  # 采标
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
        work_table.customContextMenuRequested.connect(window._on_work_table_context_menu)
        work_table.keyPressEvent = window._table_key_press_event
        return work_table, col_specs

    def setup_log_panel(self, window: QWidget, right_splitter: QSplitter) -> tuple[QTextEdit, QProgressBar]:
        """创建日志面板，返回 (log_view, progress_bar)。"""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 10, 0)

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
        window: QWidget,
        left_widget: QWidget,
        work_table: QTableWidget,
        log_view: QTextEdit,
        progress_bar: QProgressBar,
        right_splitter: QSplitter,
    ) -> QSplitter:
        """组装中央区域，返回 main_splitter。"""
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        right_splitter.addWidget(work_table)
        right_splitter.setSizes([500, 200])
        window._restore_splitter_sizes()

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([200, 700])
        window.setCentralWidget(main_splitter)
        return main_splitter

    # ================================================================
    # 状态栏 + 日志桥接
    # ================================================================

    def setup_status_bar(self, window: QWidget) -> QStatusBar:
        """创建状态栏。"""
        status_bar = QStatusBar()
        status_bar.setStyleSheet("font-size: 10pt; color: #dcdcdc;")
        status_bar.showMessage(_("ready"))
        window.setStatusBar(status_bar)
        return status_bar

    def setup_log_handler(self, log_view: QTextEdit) -> LogHandler:
        """设置日志处理器。"""
        handler = LogHandler(log_view)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
        return handler

    # ================================================================
    # 扫描器状态
    # ================================================================

    def setup_scanner(self) -> dict[str, Any]:
        """初始化扫描器状态，返回状态字典。"""
        return {
            "parsed_results": [],
            "unrecognized_files": [],
            "scan_source_root": "",
        }

    # ================================================================
    # 自动保存
    # ================================================================

    def setup_auto_save(self, window: QWidget) -> None:
        """连接自动保存信号。"""
        app = QApplication.instance()
        assert app is not None, "QApplication 未初始化"
        app.aboutToQuit.connect(self._on_auto_save)
        app.aboutToQuit.connect(window._on_shutdown_aggregator)
        atexit.register(window._on_atexit_save)
        try:
            signal.signal(signal.SIGTERM, lambda *a: self._on_auto_save())
        except (ValueError, OSError):
            pass

    def on_shutdown_aggregator(self) -> None:
        """退出前刷新聚合器中残留的通知消息（防止丢失）。"""
        try:
            from pilotstd.core.notification_aggregator import NotificationAggregator

            NotificationAggregator().shutdown()
        except Exception:
            pass

    # ================================================================
    # 工具方法
    # ================================================================

    def set_toolbar_enabled(self, toolbar_buttons: dict[str, Any], enabled: bool) -> None:
        """统一控制工具栏按钮状态。"""
        keys = (
            "btn_select",
            "btn_query",
            "btn_download",
            "btn_normalize",
            "btn_save",
            "btn_auto",
            "btn_announce",
            "btn_pause",
        )
        for key in keys:
            btn = toolbar_buttons.get(key)
            if btn is not None:
                btn.setEnabled(enabled)

    def get_library_root(self) -> str:
        """获取库根目录。"""
        from ... import core

        return core.get_library_root(self._config)
