# pilotstd/ui/main_window/_ui_setup.py
# MainWindow UI 构建混入模块
"""MainWindow UI 构建 — 菜单栏、工具栏、中央区域、系统托盘等。"""

import atexit
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

from ...i18n import _
from ...models import ParsedStdInfo
from ..table_mixin import WORK_COLUMN_KEYS, WORK_COLUMNS
from ..widgets import NotificationBellWidget
from ..workers import LogHandler

logger = logging.getLogger("pilotstd.ui")


class UISetupMixin:
    """UI 构建混入类 — 提供所有 _setup_* 方法。"""

    # ================================================================
    # 系统托盘
    # ================================================================

    def _setup_tray(self) -> None:
        """系统托盘：最小化到托盘，双击恢复。"""
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
        from ...platform.notify import NotifyService

        NotifyService.init(self._tray)

    def _on_tray_activated(self, reason: object) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    # ================================================================
    # 菜单栏
    # ================================================================

    def _setup_menu(self) -> None:
        """构建菜单栏：文件 | 工具 | 设置 | 帮助。

        所有菜单项的文本通过 _() 国际化，在 _retranslate_ui 中统一刷新。
        子菜单（如"导出工作表"）使用 addMenu 创建级联菜单。
        """
        mb = self.menuBar()
        assert mb is not None, "menuBar() 不应为 None"

        # ── 文件 ──
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

        # ── 工具 ──
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

        # ── 设置 ──
        settings_menu = mb.addMenu(_("settings"))
        settings_menu.addAction(_("preferences"), self._on_settings)

        # ── 帮助 ──
        help_menu = mb.addMenu(_("help"))
        help_menu.addAction(_("check_update"), self._on_check_update)
        help_menu.addAction(_("about"), self._on_about)

    # ================================================================
    # 工具栏
    # ================================================================

    def _setup_toolbar(self) -> None:
        """构建工具栏：导入 | 查询 | 下载 | 规范化 | 归档 | 一键处理 | 暂停 | 进度条。

        按钮使用 QPushButton + QStyle 标准图标，文本由 _retranslate_ui 国际化。
        """
        self.toolbar = QToolBar(_("toolbar_main"))
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        style = self.style()
        assert style is not None, "style() 不应为 None"

        self.btn_select = QPushButton("导入")
        self.btn_select.setIcon(style.standardIcon(style.StandardPixmap.SP_DirOpenIcon))
        self.btn_select.setToolTip("导入文件夹到项目中")
        self.btn_select.clicked.connect(self._on_select)
        self.toolbar.addWidget(self.btn_select)

        self.btn_query = QPushButton("查询")
        self.btn_query.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogContentsView))
        self.btn_query.setToolTip("对扫描后的标准号在网站上查询有效性，获取标准状态")
        self.btn_query.clicked.connect(self._on_query)
        self.toolbar.addWidget(self.btn_query)

        self.btn_download = QPushButton("下载")
        self.btn_download.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowDown))
        self.btn_download.setToolTip("对已有新版本的标准进行下载")
        self.btn_download.clicked.connect(self._on_download)
        self.toolbar.addWidget(self.btn_download)

        self.btn_normalize = QPushButton("规范化")
        self.btn_normalize.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogDetailedView))
        self.btn_normalize.setToolTip("对扫描结果生成规范标准文件名")
        self.btn_normalize.clicked.connect(self._on_normalize)
        self.toolbar.addWidget(self.btn_normalize)

        self.btn_save = QPushButton("归档")
        self.btn_save.setIcon(style.standardIcon(style.StandardPixmap.SP_DriveFDIcon))
        self.btn_save.setToolTip("将文件以规范名称保存到设定文件夹")
        self.btn_save.clicked.connect(self._on_save_to_folder)
        self.toolbar.addWidget(self.btn_save)

        self.btn_auto = QPushButton("一键处理")
        self.btn_auto.setIcon(style.standardIcon(style.StandardPixmap.SP_MediaPlay))
        self.btn_auto.setToolTip("自动依次执行 扫描→查询→下载→规范化→保存 全流程")
        self.btn_auto.clicked.connect(self._on_auto_run)
        self.toolbar.addWidget(self.btn_auto)

        self.btn_announce = QPushButton("公告检查")
        self.btn_announce.setIcon(style.standardIcon(style.StandardPixmap.SP_MessageBoxWarning))
        self.btn_announce.setToolTip("抓取国家标准/行业标准/地方标准公告，检测本地标准变更")
        self.btn_announce.clicked.connect(self._on_check_announcements)
        self.toolbar.addWidget(self.btn_announce)

        # 通知铃铛
        self.notification_bell = NotificationBellWidget(self)
        self.toolbar.addWidget(self.notification_bell)

        self.toolbar.addSeparator()

    # ================================================================
    # 中央区域（左右分栏）
    # ================================================================

    def _setup_file_tree(self) -> QWidget:
        """创建左侧文件浏览树。返回 left_widget 供布局组装。"""
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("文件导航")
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
        """创建工作表：列配置、_col_specs、行为设置、信号连接、持久化恢复。"""
        self.work_table = QTableWidget()
        self.work_table.setColumnCount(len(WORK_COLUMNS))
        self.work_table.setHorizontalHeaderLabels([_(WORK_COLUMN_KEYS[c]) for c in range(len(WORK_COLUMNS))])
        header = self.work_table.horizontalHeader()
        for c in range(len(WORK_COLUMNS)):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self._col_specs: dict[int, tuple[int, int]] = {
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
        """创建日志面板：标题标签 + 进度条 + 只读文本框。"""
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

    # ================================================================
    # 状态栏 + 日志桥接
    # ================================================================

    def _setup_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("font-size: 10pt; color: #dcdcdc;")
        self.status_bar.showMessage(_("ready"))
        self.setStatusBar(self.status_bar)

    def _setup_log_handler(self) -> None:
        handler = LogHandler(self.log_view)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
        self._log_handler = handler
        self._apply_language()
        logger.info("PilotStd 启动完成")

    # ================================================================
    # 扫描器状态
    # ================================================================

    def _setup_scanner(self) -> None:
        self._parsed_results: list[ParsedStdInfo] = []
        self._unrecognized_files: list[str] = []  # 扫描中无法识别的文件路径
        self._scan_source_root: str = ""  # 最近一次扫描的源根目录

    # ================================================================
    # 自动保存
    # ================================================================

    def _setup_auto_save(self) -> None:
        app = QApplication.instance()
        assert app is not None, "QApplication 未初始化"
        app.aboutToQuit.connect(self._on_auto_save)
        atexit.register(self._on_atexit_save)
        try:
            signal.signal(signal.SIGTERM, lambda *a: self._on_auto_save())
        except (ValueError, OSError):
            pass
