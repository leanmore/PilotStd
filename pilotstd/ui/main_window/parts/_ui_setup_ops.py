"""Extracted UI setup methods for MainWindow."""

from __future__ import annotations

import logging
import signal

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

logger = logging.getLogger("pilotstd.ui")


def _setup_tray(self) -> None:
    self._tray = QSystemTrayIcon(self)
    self._tray.setIcon(self.windowIcon())
    self._tray.setToolTip("PilotStd")
    tray_menu = QMenu()
    tray_menu.addAction(_("tray_show"), self._restore_from_tray)
    tray_menu.addSeparator()
    tray_menu.addAction(_("exit"), self._quit_app)
    self._tray.setContextMenu(tray_menu)
    self._tray.activated.connect(self._on_tray_activated)
    self._tray.show()
    from ....platform.notify import NotifyService

    NotifyService.init(self._tray)


def _on_tray_activated(self, reason: object) -> None:
    if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
        self._restore_from_tray()


def _setup_menu(self) -> None:
    mb = self.menuBar()
    assert mb is not None, "menuBar() 不应为 None"
    file_menu = mb.addMenu(_("file"))
    a = file_menu.addAction(_("open_file"), self._on_open_file)
    a.setToolTip("选择单个标准文件并导入项目")
    a = file_menu.addAction(_("open_folder"), self._on_open_folder)
    a.setToolTip("选择文件夹（含子文件夹）并导入项目")
    file_menu.addSeparator()
    save_result_menu = file_menu.addMenu(_("export_sheet"))
    save_result_menu.setToolTip("将工作区表格导出为文件")
    save_result_menu.addAction(_("export_txt"), lambda: self._on_save_result("txt"))
    save_result_menu.addAction(_("export_csv"), lambda: self._on_save_result("csv"))
    file_menu.addSeparator()
    a = file_menu.addAction(_("export_file_list"), self._on_export_file_list)
    a.setToolTip("将选中文件夹内所有文件名导出为列表（可选是否含完整路径）")
    a = file_menu.addAction(_("export_folder_tree"), self._on_export_folder_tree)
    a.setToolTip("将选中文件夹的目录树形结构导出为文本")
    file_menu.addSeparator()
    a = file_menu.addAction(_("save_query_project"), self._on_save_query_project)
    a.setToolTip("将当前查询列表保存为 .pilotstd 项目文件，便于下次恢复")
    a = file_menu.addAction(_("save_download_project"), self._on_save_download_project)
    a.setToolTip("将当前下载队列保存为 .pilotstd 项目文件，便于下次恢复")
    a = file_menu.addAction(_("import_download"), self._on_import_download)
    a.setToolTip("从文件导入标准号列表并直接下载，无需先查询")
    file_menu.addSeparator()
    a = file_menu.addAction(_("open_project"), self._on_open_project)
    a.setToolTip("从 .pilotstd 项目文件恢复之前保存的工作状态")
    file_menu.addSeparator()
    a = file_menu.addAction(_("exit"), self.close)
    a.setToolTip("退出 PilotStd（未保存的工作状态将自动保存）")
    tool_menu = mb.addMenu(_("tools"))
    rule_action = tool_menu.addAction(_("query_rules"), self._on_rule_query)
    rule_action.setToolTip("管理查询/下载网站适配规则，支持 JSON 导入导出")
    tool_menu.addAction(_("task_center"), self._on_task_center)
    tool_menu.addSeparator()
    tool_menu.addAction(_("cleanup_empty_dirs"), self._on_cleanup_empty_dirs)
    tool_menu.addAction(_("collect_unrecognized"), self._on_collect_unrecognized)
    tool_menu.addSeparator()
    tool_menu.addAction(_("export_diag"), self._on_export_diag)
    tool_menu.addSeparator()
    tool_menu.addAction(_("pending_query"), self._on_pending_query)
    settings_menu = mb.addMenu(_("settings"))
    settings_menu.addAction(_("preferences"), self._on_settings)
    help_menu = mb.addMenu(_("help"))
    help_menu.addAction(_("check_update"), self._on_check_update)
    help_menu.addAction(_("about"), self._on_about)


def _setup_toolbar(self) -> None:
    self.toolbar = QToolBar(_("toolbar_main"))
    self.toolbar.setMovable(False)
    self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)
    style = self.style()
    assert style is not None, "style() 不应为 None"
    self.btn_select = QPushButton(_("toolbar_import"))
    self.btn_select.setIcon(style.standardIcon(style.StandardPixmap.SP_DirOpenIcon))
    self.btn_select.setToolTip("导入文件夹到项目中")
    self.btn_select.clicked.connect(self._on_select)
    self.toolbar.addWidget(self.btn_select)
    self.btn_query = QPushButton(_("toolbar_query"))
    self.btn_query.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogContentsView))
    self.btn_query.setToolTip("对扫描后的标准号在网站上查询有效性，获取标准状态")
    self.btn_query.clicked.connect(self._on_query)
    self.toolbar.addWidget(self.btn_query)
    self.btn_download = QPushButton(_("toolbar_download"))
    self.btn_download.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowDown))
    self.btn_download.setToolTip("对已有新版本的标准进行下载")
    self.btn_download.clicked.connect(self._on_download)
    self.toolbar.addWidget(self.btn_download)
    self.btn_normalize = QPushButton(_("toolbar_normalize"))
    self.btn_normalize.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogDetailedView))
    self.btn_normalize.setToolTip("对扫描结果生成规范标准文件名")
    self.btn_normalize.clicked.connect(self._on_normalize)
    self.toolbar.addWidget(self.btn_normalize)
    self.btn_save = QPushButton(_("toolbar_save"))
    self.btn_save.setIcon(style.standardIcon(style.StandardPixmap.SP_DriveFDIcon))
    self.btn_save.setToolTip("将文件以规范名称保存到设定文件夹")
    self.btn_save.clicked.connect(self._on_save_to_folder)
    self.toolbar.addWidget(self.btn_save)
    self.btn_auto = QPushButton(_("toolbar_auto"))
    self.btn_auto.setIcon(style.standardIcon(style.StandardPixmap.SP_MediaPlay))
    self.btn_auto.setToolTip("自动依次执行 扫描→查询→下载→规范化→保存 全流程")
    self.btn_auto.clicked.connect(self._on_auto_run)
    self.toolbar.addWidget(self.btn_auto)
    self.btn_announce = QPushButton(_("toolbar_announce"))
    self.btn_announce.setIcon(style.standardIcon(style.StandardPixmap.SP_MessageBoxWarning))
    self.btn_announce.setToolTip("抓取国家标准/行业标准/地方标准公告，检测本地标准变更")
    self.btn_announce.clicked.connect(self._on_check_announcements)
    self.toolbar.addWidget(self.btn_announce)
    self.toolbar.addSeparator()
    self.btn_pause = QPushButton(_("toolbar_pause"))
    self.btn_pause.setIcon(style.standardIcon(style.StandardPixmap.SP_MediaPause))
    self.btn_pause.setToolTip("暂停/继续当前任务")
    self.btn_pause.clicked.connect(self._on_pause_toggle)
    self.btn_pause.setEnabled(False)
    self.toolbar.addWidget(self.btn_pause)
    self.btn_cancel = QPushButton(_("toolbar_cancel"))
    self.btn_cancel.setIcon(style.standardIcon(style.StandardPixmap.SP_DialogCancelButton))
    self.btn_cancel.setToolTip("取消当前任务")
    self.btn_cancel.clicked.connect(self._on_cancel)
    self.btn_cancel.setEnabled(False)
    self.toolbar.addWidget(self.btn_cancel)
    self.notification_bell = NotificationBellWidget(self)
    self.toolbar.addWidget(self.notification_bell)
    self.toolbar.addSeparator()


def _setup_file_tree(self) -> QWidget:
    self.file_tree = QTreeWidget()
    self.file_tree.setHeaderLabel(_("file_nav"))
    self.file_tree.setColumnCount(1)
    self.file_tree.setAnimated(True)
    self.file_tree.itemExpanded.connect(self._on_tree_item_expanded)
    self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.file_tree.customContextMenuRequested.connect(self._on_file_tree_context_menu)
    self._populate_quick_access()
    left_widget = QWidget()
    left_layout = QVBoxLayout(left_widget)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.addWidget(self.file_tree)
    return left_widget


def _setup_work_table(self) -> None:
    self.work_table = QTableWidget()
    self.work_table.setColumnCount(len(WORK_COLUMNS))
    self.work_table.setHorizontalHeaderLabels([_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS))])
    header = self.work_table.horizontalHeader()
    for c in range(len(WORK_COLUMNS)):
        header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
    header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
    self._col_specs: dict[int, tuple[int, int]] = {
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
    self.work_table.horizontalHeader().setMinimumSectionSize(30)
    for c, (w, mn) in self._col_specs.items():
        self.work_table.setColumnWidth(c, w)
    header.sectionResized.connect(self._enforce_min_column_width)
    header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    header.customContextMenuRequested.connect(self._on_header_context_menu)
    self._load_column_visibility()
    self._restore_column_widths()
    self._restore_sort_state()
    self.work_table.setAlternatingRowColors(True)
    self.work_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    self.work_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
    self.work_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
    self.work_table.setSortingEnabled(True)
    self.work_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.work_table.customContextMenuRequested.connect(self._on_work_table_context_menu)
    self.work_table.keyPressEvent = self._table_key_press_event
    self._right_splitter.addWidget(self.work_table)


def _setup_log_panel(self) -> None:
    log_widget = QWidget()
    log_layout = QVBoxLayout(log_widget)
    log_layout.setContentsMargins(0, 0, 10, 0)
    log_header = QHBoxLayout()
    log_label = QLabel(_("work_log"))
    self._log_label = log_label
    log_label.setStyleSheet("font-weight: bold; padding: 2px 4px;")
    log_header.addWidget(log_label)
    self.progress_bar = QProgressBar()
    self.progress_bar.setFormat("%p%")
    self.progress_bar.setTextVisible(True)
    self.progress_bar.setValue(0)
    log_header.addWidget(self.progress_bar, 1)
    log_layout.addLayout(log_header)
    self.log_view = QTextEdit()
    self.log_view.setReadOnly(True)
    self.log_view.setPlaceholderText(_("log_placeholder"))
    log_layout.addWidget(self.log_view)
    self._right_splitter.addWidget(log_widget)


def _setup_central(self) -> None:
    self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
    self._right_splitter = QSplitter(Qt.Orientation.Vertical)
    left_widget = self._setup_file_tree()
    self._setup_work_table()
    self._setup_log_panel()
    self._right_splitter.setSizes([500, 200])
    self._restore_splitter_sizes()
    self._main_splitter.addWidget(left_widget)
    self._main_splitter.addWidget(self._right_splitter)
    self._main_splitter.setStretchFactor(0, 0)
    self._main_splitter.setStretchFactor(1, 1)
    self._main_splitter.setSizes([200, 700])
    self.setCentralWidget(self._main_splitter)


def _setup_status_bar(self) -> None:
    self.status_bar = QStatusBar()
    self.status_bar.setStyleSheet("font-size: 10pt; color: #dcdcdc;")
    self.status_bar.showMessage(_("ready"))
    self.setStatusBar(self.status_bar)


def _setup_log_handler(self) -> None:
    from ...workers import LogHandler

    handler = LogHandler(self.log_view)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
    self._log_handler = handler
    self._apply_language()
    logger.info("PilotStd 启动完成")


def _setup_scanner(self) -> None:
    from ....models import ParsedStdInfo

    self._parsed_results: list[ParsedStdInfo] = []
    self._unrecognized_files: list[str] = []
    self._scan_source_root: str = ""


def _setup_auto_save(self) -> None:
    app = QApplication.instance()
    assert app is not None, "QApplication 未初始化"
    app.aboutToQuit.connect(self._on_auto_save)
    app.aboutToQuit.connect(self._on_shutdown_aggregator)
    import atexit

    atexit.register(self._on_atexit_save)
    try:
        signal.signal(signal.SIGTERM, lambda *a: self._on_auto_save())
    except (ValueError, OSError):
        pass


def _on_shutdown_aggregator(self) -> None:
    try:
        from pilotstd.core.notification_aggregator import NotificationAggregator

        NotificationAggregator().shutdown()
    except Exception:
        pass
